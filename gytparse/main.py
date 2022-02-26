import urllib
import sys
import gi
import shutil
from functools import partial

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import GObject, Gtk, Adw, Gio, GLib, Gdk, GdkPixbuf

from .operation import PageFetcher, ThumbFetcher

def _set_css_class(wdg, cls):
    Gtk.StyleContext.add_class(Gtk.Widget.get_style_context(wdg), cls)


@Gtk.Template(resource_path='/gr/oscillate/gytparse/main.ui')
class MainWindow(Adw.ApplicationWindow):

    __gtype_name__ = 'MainWindow'

    ui_button = Gtk.Template.Child()
    ui_entry = Gtk.Template.Child()
    scrolled_win = Gtk.Template.Child()
    list_box = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.morerow = None
        self.css_provider = Gtk.CssProvider()
        self.css_provider.load_from_resource('/gr/oscillate/gytparse/main.css')
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),
            self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        _set_css_class(self.list_box, 'list_box')

    @Gtk.Template.Callback()
    def ui_button_clicked(self, *args):
        self.__submit_new(self.ui_entry.get_text())
        self.ui_entry.grab_focus()
        pass

    @Gtk.Template.Callback()
    def ui_entry_activated(self, *args):
        self.__submit_new(self.ui_entry.get_text())

    def videos_found(self, fetcher, result, clear=True):
        self.ui_button.set_sensitive(True)
        self.ui_entry.set_sensitive(True)
        self.ui_entry.grab_focus()
        (videos, apikey, continuation) = fetcher.get_results(result)

        if videos is None:
            return

        self.__remove_more_widget()
        if clear:
            self.__clear_listbox()

        for v in videos:
            entry = EntryContainer(v)
            row = Gtk.ListBoxRow()
            row.set_property('activatable', False)
            row.set_child(entry)
            _set_css_class(row, 'entry')
            self.list_box.append(row)

        self.__add_more_widget(apikey, continuation)

    def __submit_new(self, query):
        fetcher = PageFetcher()
        fetcher.fetch_async(None, self.videos_found, query=query)
        self.scrolled_win.grab_focus()
        self.ui_button.set_sensitive(False)
        self.ui_entry.set_sensitive(False)

    def __submit_continue(self, apikey, continuation):
        fetcher = PageFetcher()
        fetcher.fetch_async(None, \
            partial(self.videos_found, clear=False), query=None,
            apikey=apikey, continuation=continuation)
        self.scrolled_win.grab_focus()
        self.ui_button.set_sensitive(False)
        self.ui_entry.set_sensitive(False)
        self.morerow.set_sensitive(False)

    def __clear_listbox(self):

        while True:
            row = self.list_box.get_row_at_index(0)
            if row is None:
                break
            else:
                self.list_box.remove(row)

    def __add_more_widget(self, apikey, continuation):

        self.morerow = Gtk.ListBoxRow()
        self.morerow.set_property('activatable', False)
        morewidget = MoreWidget(apikey, continuation)
        morewidget.connect("request-more", self.__more_requested)
        self.morerow.set_child(morewidget)
        self.list_box.append(self.morerow)

    def __remove_more_widget(self):
        if self.morerow is not None:
            self.list_box.remove(self.morerow)
            del self.morerow
            self.morerow = None

    def __more_requested(self, _, apikey, continuation):
        self.__submit_continue(apikey, continuation)


@Gtk.Template(resource_path='/gr/oscillate/gytparse/entry.ui')
class EntryContainer(Adw.Bin):

    __gtype_name__ = 'EntryContainer'

    layout_box = Gtk.Template.Child()
    entry_title = Gtk.Template.Child()
    entry_subtitle = Gtk.Template.Child()
    entry_uploader = Gtk.Template.Child()

    def __init__(self, video, **kwargs):
        super().__init__(**kwargs)
        self.entry_title.set_markup('<a class="title_link" href="https://youtu.be/%s">%s</a>' %
            (urllib.parse.quote_plus(video.videoId), html.escape(video.title)))
        if video.uploaded is None or video.uploaded != "":
            self.entry_subtitle.set_text("%s views · %s" % (video.views, video.uploaded))
        else:
            self.entry_subtitle.set_text("%s views" % video.views)
        self.entry_uploader.set_text(video.uploader)
        self.video = video

        fetcher = ThumbFetcher(video.thumbnail)
        fetcher.fetch_async(None, self.thumb_found)

    def thumb_found(self, fetcher, result):
        thumb = fetcher.get_pixbuf(result)
        if thumb is not None:
            self.entry_img = Gtk.Picture.new_for_pixbuf(thumb)
            self.entry_img.set_property('width_request', thumb.get_width())
            self.entry_img.set_property('height_request', thumb.get_height())
            self.entry_img.set_property('can_shrink', True)
            #self.entry_img.set_property('keep_aspect_ratio', True)
            self.entry_img.set_hexpand(False)

            widget = Adw.Bin()
            widget.set_property('width_request', thumb.get_width())
            widget.set_property('height_request', thumb.get_height())
            overlay = Gtk.Overlay()
            label = Gtk.Label()
            _set_css_class(label, 'duration_label')
            label.set_text(self.video.duration)
            label.set_property('halign', Gtk.Align.END)
            label.set_property('valign', Gtk.Align.END)
            label.set_property('vexpand', False)
            label.set_property('hexpand', False)
            widget.set_child(overlay)

            overlay.add_overlay(widget=self.entry_img)
            overlay.add_overlay(widget=label)

            _set_css_class(self.entry_img, 'entry_img')
            self.layout_box.prepend(widget)

    @Gtk.Template.Callback()
    def entry_play_clicked(self, *args):
        mpv = shutil.which('mpv')
        if mpv is None:
            return

        uri = "https://youtu.be/%s" % urllib.parse.quote_plus(self.video.videoId)
        flags = GLib.SPAWN_DO_NOT_REAP_CHILD|GLib.SPAWN_STDERR_TO_DEV_NULL|GLib.SPAWN_STDOUT_TO_DEV_NULL
        command = GLib.spawn_async([mpv, uri], flags=flags)

    @Gtk.Template.Callback()
    def entry_open_clicked(self, *args):
        uri = "https://youtu.be/%s" % urllib.parse.quote_plus(self.video.videoId)
        Gio.AppInfo.launch_default_for_uri(uri, None)


@Gtk.Template(resource_path='/gr/oscillate/gytparse/more.ui')
class MoreWidget(Adw.Bin):

    __gtype_name__ = 'MoreWidget'

    def __init__(self, apikey, continuation, **kwargs):
        super().__init__(**kwargs)
        self.apikey = apikey
        self.continuation = continuation

    @GObject.Signal(arg_types=(str, str, ))
    def request_more(self, apikey, continuation):
        pass

    @Gtk.Template.Callback()
    def more_clicked(self, *args):
        self.emit("request-more", self.apikey, self.continuation)


class Application(Gtk.Application):

    def __init__(self):
        super().__init__(application_id="gr.oscillate.gytparse", \
            flags=Gio.ApplicationFlags.FLAGS_NONE)
        GLib.set_application_name('YouTube Parser')
        GLib.set_prgname("gr.oscillate.gytparse")

    def do_startup(self):
        Gtk.Application.do_startup(self)
        Adw.init()

    def do_activate(self):
        win = self.props.active_window

        if not win:
            win = MainWindow(application=self)

        win.present()


def main(*args):

    app = Application()
    app.run(sys.argv)
