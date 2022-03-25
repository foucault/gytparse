import sys
import os
import os.path
import signal
import requests
import shutil
import time
from functools import partial
from . import youtube

from gi.repository import GLib, Gio, GObject, GdkPixbuf

from .settings import Settings

try:
    import yt_dlp as youtube_dl
    YTDLNAME = 'yt-dlp'
except ModuleNotFoundError:
    import youtube_dl
    YTDLNAME = 'youtube-dl'


_FORMAT_TMPL = 'bestvideo[height<=?%d]+bestaudio/best[height<=?%d]'


def ytdl_fmt_from_str(quality):

    if quality not in ['best', '2160p', '1080p', '720p', '480p', '360p']:
        raise ValueError("Unsupported video quality: " + quality)

    if quality == 'best':
        return 'bestvideo+bestaudio/best'
    else:
        quality = int(quality[:-1])
        return _FORMAT_TMPL % (quality, quality)


class _VideoFetchLogger:

    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        print('An error occurred while downloading:', msg, file=sys.stderr)


class VideoFetcher(GObject.GObject):

    def __init__(self):
        super().__init__()
        self.videos = []
        self.running = False

    def queue_video(self, url, target):
        self.videos.append(\
            {'url': url, 'target': target, 'offset': 0, 'totalsize': 0, \
             'running': False, 'pid': -1})

    def unqueue_video(self, url):
        for v in self.videos:
            if v['url'] == url:
                self.__kill_process(v)

    def __extract_filesize(self, url):
        ydl = youtube_dl.YoutubeDL({
            'format': ytdl_fmt_from_str(Settings.get_string('download-quality')),
            'logger': _VideoFetchLogger()})
        result = ydl.extract_info(url, download=False)
        totalfilesize = 0
        for fmt in result['requested_formats']:
            totalfilesize += fmt['filesize']

        return totalfilesize

    def __reap_child(self, pid, status, video):
        print('Reapping PID', pid, 'status:', status)
        GLib.spawn_close_pid(pid)
        self.video_finished.emit(video['url'])
        video['running'] = False
        self.videos.pop(0)

    def __kill_process(self, video):
        print('Killing PID', video['pid'])
        pid = video['pid']
        if pid > 0:
            os.kill(pid, signal.SIGINT)

    def __fetch_inner(self, video):
        url = video['url']
        target = video['target']

        ytdl = shutil.which(YTDLNAME)
        if ytdl is None:
            return

        fmt = ytdl_fmt_from_str(Settings.get_string('download-quality'))
        proxy = Settings.proxy_url()
        flags = GLib.SPAWN_DO_NOT_REAP_CHILD | GLib.SPAWN_STDERR_TO_DEV_NULL
        video['totalsize'] = self.__extract_filesize(url)

        cmd = [ytdl]
        if proxy is not None:
            cmd.append('--proxy=%s' % proxy)
        cmd.append('--quiet')
        cmd.append('--format=%s' % fmt)
        cmd.append('--progress')
        cmd.append('--progress-template=%(progress.status)s;;%(progress.downloaded_bytes)d')
        if Settings.get_string('output-merge-format') != 'automatic':
            cmd.append("--merge-output-format=%s" % Settings.get_string('output-merge-format'))
        cmd.append('--output='+ os.path.join(target, '%(title)s.%(ext)s'))
        cmd.append(video['url'])

        self.video_starting.emit(url, video['totalsize'])
        video['running'] = True
        (pid, _, cstdout, _) = \
            GLib.spawn_async(cmd, standard_output=True, standard_error=False, flags=flags)
        video['pid'] = pid
        GLib.child_watch_add(\
            GLib.PRIORITY_DEFAULT_IDLE, pid, \
            partial(self.__reap_child, video=video))

        with os.fdopen(cstdout, 'r') as fh:
            while video['running']:
                if video['offset'] >= video['totalsize']:
                    # download has finished and video is muxing
                    # wait for ytdl to exit
                    time.sleep(0.1)
                    continue
                try:
                    (status, received) = fh.readline().strip().split(';;')
                except ValueError:
                    continue
                received = int(received)
                if status == 'downloading':
                    total_so_far = video['offset'] + received
                    self.video_progress.emit(video['url'], total_so_far, video['totalsize'])
                elif status == 'finished':
                    video['offset'] += received

    def fetch(self):

        self.running = True
        while len(self.videos) > 0:
            video = self.videos[0]
            self.__fetch_inner(video)
        self.running = False

    def fetch_async(self, cancellable=None, callback=None):

        if self.running:
            return

        def fetch_in_thread(task, self, data, cancellable):
            res = self.fetch()
            task.return_value(True)

        task = Gio.Task.new(self, cancellable, callback)
        task.run_in_thread(fetch_in_thread)

    @GObject.Signal(arg_types=(str, int))
    def video_starting(self, url, size):
        pass

    @GObject.Signal(arg_types=(str,))
    def video_finished(self, url):
        pass

    @GObject.Signal(arg_types=(str, int, int))
    def video_progress(self, url, bytes_downloaded, bytes_total):
        pass


class VideoMetadataFetcher(GObject.GObject):

    def __init__(self, url):
        super().__init__()
        self.url = url
        self.totalsize = 0

    def fetch(self):
        opts = { 'logger': _VideoFetchLogger(),
                 'format': ytdl_fmt_from_str(Settings.get_string('download-quality')),
        }

        if Settings.proxy_url() is not None:
            opts['proxy'] = Settings.proxy_url()

        with youtube_dl.YoutubeDL(opts) as ydl:
            result = ydl.extract_info(self.url, download=False)
            for fmt in result['requested_formats']:
                self.totalsize += fmt['filesize']

    def fetch_async(self, cancellable=None, callback=None):
        def fetch_in_thread(task, self, data, cancellable):
            res = self.fetch()
            data = self.__make_data()
            task.return_value(data)

        task = Gio.Task.new(self, cancellable, callback)
        task.run_in_thread(fetch_in_thread)

    def get_metadata(self, result):
        val = result.propagate_value()
        if val[0]:
            return val[1]
        return None

    def __make_data(self):
        return { 'filesize': self.totalsize }


class ThumbFetcher(GObject.GObject):

    def __init__(self, thumburl):
        super().__init__()
        self.thumburl = thumburl
        self.pixbuf = None

    def fetch(self):

        def resize(img, w, h):
            img.set_size(200, 112)

        resp = requests.get(self.thumburl)

        if not resp.ok:
            return

        data = resp.content
        loader = GdkPixbuf.PixbufLoader()
        loader.connect('size-prepared', resize)
        loader.write(data)
        loader.close()

        pixbuf = loader.get_pixbuf()
        self.pixbuf = pixbuf

    def fetch_async(self, cancellable, callback):

        def fetch_in_thread(task, self, data, cancellable):
            res = self.fetch()
            task.return_value(self.pixbuf)

        task = Gio.Task.new(self, cancellable, callback)
        task.run_in_thread(fetch_in_thread)

    def get_pixbuf(self, result):
        val = result.propagate_value()
        if val[0]:
            return val[1]
        return None


class PageFetcher(GObject.GObject):

    def __init__(self):
        super().__init__()
        self.videos = []
        self.apikey = ''
        self.continuation = ''

    def fetch(self, query=None, apikey=None, continuation=None):

        if apikey is None and continuation is None:
            (sections, apikey, continuation) = youtube.yt_search(query, proxy=Settings.proxy_url())
        else:
            (sections, apikey, continuation) = youtube.yt_token_search(apikey, continuation,
                proxy=Settings.proxy_url())

        self.apikey = apikey
        self.continuation = continuation

        for section in sections:
            if 'itemSectionRenderer' not in section.keys():
                continue
            contents = section['itemSectionRenderer']['contents']

            for entry in contents:
                try:
                    result_type = list(entry.keys())[0]
                except IndexError:
                    continue

                if result_type == 'videoRenderer':
                    video = youtube.Video.from_dict(entry['videoRenderer'])
                    self.videos.append(video)
                else:
                    continue

    def fetch_async(self, cancellable, callback, query=None, apikey=None, continuation=None):

        def fetch_in_thread(task, self, data, cancellable):
            res = self.fetch(query, apikey, continuation)
            task.return_value((self.videos, self.apikey, self.continuation))

        task = Gio.Task.new(self, cancellable, callback)
        task.run_in_thread(fetch_in_thread)

    def get_results(self, result):
        val = result.propagate_value()
        if val[0]:
            return val[1]
        return None
