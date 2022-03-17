import urllib
import html
import sys
import gi
import shutil
import math
import os.path
from functools import partial

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import GObject, Gtk, Adw, Gio, GLib, Gdk, GdkPixbuf

from .operation import PageFetcher, ThumbFetcher, VideoFetcher
from .operation import VideoMetadataFetcher, ytdl_fmt_from_str
from .settings import Settings, Secrets


def _pretty_print_size(size):

    if size == 0:
        return "0 B"

    units = ('B', 'kiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB')

    idx = int(math.floor(math.log(size, 1024)))
    power = math.pow(1024, idx)
    csize = round(size / power, 2)

    return "%s %s" % (csize, units[idx])


def _set_css_class(wdg, cls):
    Gtk.StyleContext.add_class(Gtk.Widget.get_style_context(wdg), cls)


@Gtk.Template(resource_path='/gr/oscillate/gytparse/main.ui')
class MainWindow(Adw.ApplicationWindow):

    __gtype_name__ = 'MainWindow'

    ui_button = Gtk.Template.Child()
    ui_entry = Gtk.Template.Child()
    scrolled_win = Gtk.Template.Child()
    list_box = Gtk.Template.Child()
    dl_list_box = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.morerow = None
        self.video_fetcher = VideoFetcher()
        self.video_fetcher.connect('video-progress', self.__video_progress)
        self.video_fetcher.connect('video-finished', self.__video_completed)
        self.dls_queued = {}

        self.css_provider = Gtk.CssProvider()
        self.css_provider.load_from_resource('/gr/oscillate/gytparse/main.css')
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),
            self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        _set_css_class(self.list_box, 'list_box')
        self.set_icon_name('gr.oscillate.gytparse')

        self.set_property('default-width', Settings.get_int('window-width'))
        self.set_property('default-height', Settings.get_int('window-height'))

        self.shortcuts = Gtk.ShortcutController()
        self.shortcuts.set_scope(Gtk.ShortcutScope.GLOBAL)
        self.add_controller(self.shortcuts)
        self.__install_global_shortcut('<ctrl>l', lambda *args: self.ui_entry.grab_focus())

    def __install_global_shortcut(self, keybinding, callback):
        shortcut = Gtk.Shortcut()
        trigger = Gtk.ShortcutTrigger.parse_string(keybinding)
        shortcutaction = Gtk.CallbackAction.new(callback, None)
        shortcut.set_trigger(trigger)
        shortcut.set_action(shortcutaction)
        self.shortcuts.add_shortcut(shortcut)

    @Gtk.Template.Callback()
    def ui_button_clicked(self, *args):
        self.__submit_new(self.ui_entry.get_text())
        self.ui_entry.grab_focus()
        pass

    @Gtk.Template.Callback()
    def ui_entry_activated(self, *args):
        self.__submit_new(self.ui_entry.get_text())

    @Gtk.Template.Callback()
    def open_preferences_clicked(self, *args):
        app = self.get_application()
        win = app.get_active_window()
        preferences = PreferencesWindow()
        preferences.set_transient_for(win)
        preferences.present()

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
            entry.connect('dl-request', self.__add_new_dl_request)

        self.__add_more_widget(apikey, continuation)
        if clear:
            self.scrolled_win.get_vadjustment().set_value(0);

    def __video_progress(self, fetcher, url, bytes_downloaded, total):
        entry = self.dls_queued[url].get_child()
        entry.set_progress(bytes_downloaded/total)

    def __video_completed(self, fetcher, url):
        entry = self.dls_queued[url].get_child()
        entry.set_completed()

    def __video_cancel(self, _, url):
        self.video_fetcher.unqueue_video(url)

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

    def __add_new_dl_request(self, _, title, uri, folder, pixbuf):
        row = Gtk.ListBoxRow()
        row.set_property('activatable', False)
        container = DlEntryContainer(title, uri, folder, pixbuf)
        container.connect('video-request-cancel', self.__video_cancel)
        row.set_child(container)
        self.dls_queued[uri] = row
        self.dl_list_box.append(row)
        self.video_fetcher.queue_video(uri, folder)
        self.video_fetcher.fetch_async()


@Gtk.Template(resource_path='/gr/oscillate/gytparse/entry.ui')
class EntryContainer(Adw.Bin):

    __gtype_name__ = 'EntryContainer'

    layout_box = Gtk.Template.Child()
    entry_title = Gtk.Template.Child()
    entry_subtitle = Gtk.Template.Child()
    entry_uploader = Gtk.Template.Child()
    entry_snippet = Gtk.Template.Child()

    def __init__(self, video, **kwargs):
        super().__init__(**kwargs)
        self.entry_title.set_markup('<a class="title_link" href="https://youtu.be/%s">%s</a>' %
            (urllib.parse.quote_plus(video.videoId), html.escape(video.title)))
        if video.uploaded is None or video.uploaded != "":
            self.entry_subtitle.set_text("%s views · %s" % (video.views, video.uploaded))
        else:
            self.entry_subtitle.set_text("%s views" % video.views)
        self.entry_uploader.set_text(video.uploader)
        if video.snippet != "":
            self.entry_snippet.set_text(video.snippet)
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

        if Settings.get_boolean('override-mpv-path'):
            mpv = Settings.get_string('mpv-path')
        else:
            mpv = shutil.which('mpv')

        if mpv is None:
            error_msg = _("No valid 'mpv' executable found")
        elif not os.path.exists(mpv):
            error_msg = _("Executable '%s' not found") % mpv
        else:
            error_msg = None

        if error_msg:
            dialog = Gtk.MessageDialog(transient_for=self.get_root(), \
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CLOSE, \
                text=error_msg)
            dialog.set_modal(True)
            dialog.connect('response', lambda dlg, _: dlg.destroy())
            dialog.show()
            return

        fmt = ytdl_fmt_from_str(Settings.get_string('stream-quality'))

        uri = "https://youtu.be/%s" % urllib.parse.quote_plus(self.video.videoId)
        flags = GLib.SPAWN_DO_NOT_REAP_CHILD|GLib.SPAWN_STDERR_TO_DEV_NULL|GLib.SPAWN_STDOUT_TO_DEV_NULL
        proxy = Settings.proxy_url()
        if proxy is None:
            command = GLib.spawn_async([mpv, "--ytdl-format=%s" % fmt, uri], flags=flags)
        elif Settings.get_string('proxy-type') == 'socks5':
            dialog = Gtk.MessageDialog(transient_for=self.get_root(), \
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CLOSE, \
                text=_("Streaming is not supported over socks proxies"))
            dialog.set_modal(True)
            dialog.connect('response', lambda dlg, _: dlg.destroy())
            dialog.show()
            return
        else:
            command = GLib.spawn_async([mpv, "--ytdl-format=%s" % fmt, \
                "--ytdl-raw-options-append=proxy=%s" % proxy, uri], flags=flags)

    @Gtk.Template.Callback()
    def entry_save_clicked(self, *args):

        def callback(chooser, response):
            if response == Gtk.ResponseType.ACCEPT:
                uri = "https://youtu.be/%s" % urllib.parse.quote_plus(self.video.videoId)
                self.dl_request.emit(self.video.title, uri, \
                    chooser.get_file().get_path(),\
                    self.entry_img.get_paintable())


        parent = self.get_root()
        self.dialog = Gtk.FileChooserNative.new(title="Select folder",
            parent=parent, action=Gtk.FileChooserAction.SELECT_FOLDER)
        self.dialog.set_modal(True)
        self.dialog.show()
        self.dialog.connect("response", callback)

    @GObject.Signal(arg_types=(str, str, str, object))
    def dl_request(self, name, uri, folder, pixbuf):
        pass


@Gtk.Template(resource_path='/gr/oscillate/gytparse/more.ui')
class MoreWidget(Adw.Bin):

    __gtype_name__ = 'MoreWidget'

    more_button = Gtk.Template.Child()

    def __init__(self, apikey, continuation, **kwargs):
        super().__init__(**kwargs)
        self.apikey = apikey
        self.continuation = continuation
        self.more_button.set_label(_("Fetch more"))

    @GObject.Signal(arg_types=(str, str, ))
    def request_more(self, apikey, continuation):
        pass

    @Gtk.Template.Callback()
    def more_clicked(self, *args):
        self.emit("request-more", self.apikey, self.continuation)


@Gtk.Template(resource_path='/gr/oscillate/gytparse/dlentry.ui')
class DlEntryContainer(Adw.Bin):

    __gtype_name__ = 'DlEntryContainer'

    dl_title_label = Gtk.Template.Child()
    dl_subtitle_label = Gtk.Template.Child()
    dl_filesize_label = Gtk.Template.Child()
    layout_box = Gtk.Template.Child()
    dl_progressbar = Gtk.Template.Child()

    def __init__(self, title, uri, folder, pixbuf, **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.uri = uri
        self.folder = folder
        self.dl_title_label.set_text(title)
        self.dl_subtitle_label.set_text('Added')
        self.filesize = 0

        self.entry_img = Gtk.Picture.new_for_paintable(pixbuf)
        self.entry_img.set_property('width_request', pixbuf.get_width()*0.25)
        self.entry_img.set_property('height_request', pixbuf.get_height()*0.25)
        self.entry_img.set_property('can_shrink', True)
        self.entry_img.set_hexpand(False)
        self.layout_box.prepend(self.entry_img)

        fetcher = VideoMetadataFetcher(self.uri)
        fetcher.fetch_async(None, self.metadata_found)

    def __update_progress_cb(self, progress):
        self.dl_progressbar.set_fraction(progress)
        self.dl_subtitle_label.set_text("Downloading… – %3d%%" %
            (int(progress*100.0)))

    def set_progress(self, progress):
        GLib.idle_add(self.__update_progress_cb, progress)

    def set_completed(self):
        self.dl_progressbar.set_fraction(1.0)
        self.dl_subtitle_label.set_text("Completed – Saved to: %s" % (self.folder))

    def metadata_found(self, fetcher, result):
        metadata = fetcher.get_metadata(result)
        self.filesize = metadata['filesize']
        self.dl_filesize_label.set_text(_pretty_print_size(self.filesize))

    @GObject.Signal(arg_types=(str, ))
    def video_request_cancel(self, url):
        pass

    @Gtk.Template.Callback()
    def open_folder_clicked(self, *args):
        Gtk.show_uri(None, "file://"+self.folder, Gdk.CURRENT_TIME)

    @Gtk.Template.Callback()
    def cancel_clicked(self, *args):
        self.video_request_cancel.emit(self.uri)


@Gtk.Template(resource_path='/gr/oscillate/gytparse/preferences.ui')
class PreferencesWindow(Adw.PreferencesWindow):

    __gtype_name__ = 'PreferencesWindow'

    download_quality_row = Gtk.Template.Child()
    stream_quality_row = Gtk.Template.Child()
    proxy_type_row = Gtk.Template.Child()
    proxy_host_entry = Gtk.Template.Child()
    proxy_port_spin = Gtk.Template.Child()
    proxy_username_entry = Gtk.Template.Child()
    proxy_password_entry = Gtk.Template.Child()
    proxy_host_row = Gtk.Template.Child()
    proxy_port_row = Gtk.Template.Child()
    proxy_auth_expander_row = Gtk.Template.Child()
    mpv_path_row = Gtk.Template.Child()
    mpv_path_entry = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__populate_combobox('download-quality', self.download_quality_row)
        self.__populate_combobox('stream-quality', self.stream_quality_row)
        self.proxy_host_entry.set_text(Settings.get_string('proxy-host'))
        self.proxy_port_spin.set_value(Settings.get_int('proxy-port'))
        self.proxy_password_entry.connect('changed', self.__on_password_changed)

        Settings.bind('proxy-host', self.proxy_host_entry, 'text', \
            Gio.SettingsBindFlags.DEFAULT | Gio.SettingsBindFlags.NO_SENSITIVITY)
        Settings.bind('proxy-port', self.proxy_port_spin, 'value', \
            Gio.SettingsBindFlags.DEFAULT | Gio.SettingsBindFlags.NO_SENSITIVITY)
        Settings.bind('enable-proxy-auth', self.proxy_auth_expander_row, 'enable-expansion', \
            Gio.SettingsBindFlags.DEFAULT)
        Settings.bind('proxy-auth-username', self.proxy_username_entry, 'text', \
            Gio.SettingsBindFlags.DEFAULT)
        Settings.bind('mpv-path', self.mpv_path_entry, 'text', \
            Gio.SettingsBindFlags.DEFAULT | Gio.SettingsBindFlags.NO_SENSITIVITY)
        Settings.bind('override-mpv-path', self.mpv_path_row, 'enable-expansion', \
            Gio.SettingsBindFlags.DEFAULT | Gio.SettingsBindFlags.NO_SENSITIVITY)

        self.__populate_combobox('proxy-type', self.proxy_type_row)

        pw = Secrets.get(Settings.get_string('proxy-auth-username'))
        if pw is not None:
            self.proxy_password_entry.set_text(pw)

    def __populate_combobox(self, key, combo):
        schema = Settings.get_property('settings-schema')
        try:
            choices = schema.get_key(key).get_range()[1]
            value = Settings.get_string(key)
            model = combo.get_model()
            for (i, c) in enumerate(choices):
                model.append(c)
                if c == value:
                    combo.set_selected(i)
        except Exception as exc:
            print("Could not populate combo from key", key, exc, file=sys.stderr)

    def __on_password_retrieved(self, _, result):
        pw = Secret.password_lookup_finish(result)
        if pw is not None:
            self.proxy_password_entry.set_text(pw)

    def __on_password_changed(self, wdg):
        uname = Settings.get_string('proxy-auth-username')
        pw = wdg.get_text()
        Secrets.set(uname, pw)


    @Gtk.Template.Callback()
    def combo_value_changed(self, combo, _):
        if combo == self.proxy_type_row:
            proxy = self.proxy_type_row.get_selected_item().get_string()
            self.proxy_host_row.set_sensitive(proxy != 'none')
            self.proxy_host_row.set_selectable(proxy != 'none')
            self.proxy_host_row.set_activatable(proxy != 'none')
            self.proxy_port_row.set_sensitive(proxy != 'none')
            self.proxy_port_row.set_selectable(proxy != 'none')
            self.proxy_port_row.set_activatable(proxy != 'none')
            self.proxy_auth_expander_row.set_sensitive(proxy != 'none')
            self.proxy_auth_expander_row.set_selectable(proxy != 'none')
            self.proxy_auth_expander_row.set_activatable(proxy != 'none')
            Settings.set_string('proxy-type', proxy)
        elif combo == self.download_quality_row:
            dlquality = self.download_quality_row.get_selected_item().get_string()
            Settings.set_string('download-quality', dlquality)
        elif combo == self.stream_quality_row:
            strquality = self.stream_quality_row.get_selected_item().get_string()
            Settings.set_string('stream-quality', strquality)
        else:
            print('combo_value_changed called on unknown widget', combo, \
                file=sys.stderr)

class Application(Gtk.Application):

    def __init__(self):
        super().__init__(application_id="gr.oscillate.gytparse", \
            flags=Gio.ApplicationFlags.FLAGS_NONE)
        GLib.set_application_name('YouTube Parser')
        GLib.set_prgname("gr.oscillate.gytparse")
        self.connect('window-removed', self.window_removed)

    def window_removed(self, _, window):
        (w, h) = window.get_default_size()
        Settings.set_int('window-width', w)
        Settings.set_int('window-height', h)

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
