import os.path
import requests
from functools import partial
from . import youtube

from gi.repository import GLib, Gio, GObject, GdkPixbuf

try:
    import yt_dlp as youtube_dl
except ModuleNotFoundError:
    import youtube_dl


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
        self.videos.append({'url': url, 'target': target, 'offset': 0, 'totalsize': 0})

    def __fetch_inner(self, video):
        url = video['url']
        target = video['target']

        def hook(data, video):
            if data['status'] == 'downloading':
                total_so_far = video['offset'] + data['downloaded_bytes']
                self.video_progress.emit(video['url'], total_so_far, video['totalsize'])
            elif data['status'] == 'finished':
                video['offset'] = data['downloaded_bytes']

        opts = {
            'outtmpl': os.path.join(target, '%(title)s.%(ext)s'),
            'progress_hooks': [partial(hook, video=video)],
            'logger': _VideoFetchLogger()
        }

        with youtube_dl.YoutubeDL(opts) as ydl:
            result = ydl.extract_info(url, download=False)
            totalfilesize = 0
            for fmt in result['requested_formats']:
                totalfilesize += fmt['filesize']

            video['totalsize'] = totalfilesize

        self.video_starting.emit(url, video['totalsize'])
        with youtube_dl.YoutubeDL(opts) as ydl:
            ydl.download([url])
        self.video_finished.emit(url)

    def fetch(self):

        self.running = True
        while len(self.videos) > 0:
            video = self.videos.pop(0)
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
        opts = { 'logger': _VideoFetchLogger() }

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
            (sections, apikey, continuation) = youtube.yt_search(query)
        else:
            (sections, apikey, continuation) = youtube.yt_token_search(apikey, continuation)

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
