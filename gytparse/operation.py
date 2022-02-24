import requests
from . import youtube

from gi.repository import GLib, Gio, GObject, GdkPixbuf


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
