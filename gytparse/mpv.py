import io
import os
import os.path
import socket
import json
import time
import threading

from .settings import Settings, RUNTIME_DIR
from .operation import ytdl_fmt_from_str
from gi.repository import GLib, GObject


class _MPVThread(threading.Thread, GObject.GObject):
    def __init__(self, mpvpath, url):
        GObject.GObject.__init__(self)
        threading.Thread.__init__(self)
        self.running = False
        self.url = url
        self.mpvpath = mpvpath
        self.replacing = False
        self.socket_path = os.path.join(RUNTIME_DIR, 'gytparse_mpvsock')

    def run(self):

        fmt = ytdl_fmt_from_str(Settings.get_string('stream-quality'))
        proxy = Settings.proxy_url()
        flags = GLib.SPAWN_STDERR_TO_DEV_NULL|GLib.SPAWN_STDOUT_TO_DEV_NULL
        GLib.spawn_async([self.mpvpath, "--idle=once", "--input-ipc-server=%s" % \
            self.socket_path], flags=flags)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        connection_attempts = 0
        while True:
            try:
                self.sock.connect(self.socket_path)
                break
            except (FileNotFoundError, ConnectionRefusedError) as exc:
                # waiting for port to come up
                connection_attempts += 1
                if connection_attempts < 10:
                    time.sleep(0.2)
                else:
                    # can't connect; something is wrong
                    err = "Could not connect to MPV %s" % str(exc)
                    self.video_loading_failed.emit(err)
                    return

        self.channel = self.sock.makefile(mode='rw', newline='\n')

        self.sock.send(b'{"command": ["set_property", "ytdl-format", "%s"]}\n' % fmt.encode())
        self.channel.readline()

        if proxy is not None and not proxy.lower().startswith('socks5:'):
            self.sock.send(b'{"command": ["set_property", "http-proxy", "%s"]}\n' % proxy.encode())
            self.channel.readline()

        startcmd = '{"command": ["loadfile", "%s"]}\n' % self.url
        self.sock.send(startcmd.encode())
        self.channel.readline()

        while True:
            data = json.loads(self.channel.readline())
            try:
                evt = data['event']
                if evt == 'file-loaded':
                    self.video_loaded.emit()
                elif evt == 'end-file':
                    # end-file will still be emitted when
                    # a new video is requested, so check
                    # if this is a replacement operation
                    # or a genuine EOF
                    if self.replacing:
                        self.replacing = False
                    else:
                        break
            except KeyError:
                continue

        self.video_finished.emit()
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)
        self.channel.close()
        self.sock.close()

    def replace_url(self, url):
        self.url = url
        self.replacing = True
        startcmd = '{"command": ["loadfile", "%s"]}\n' % self.url
        self.sock.send(startcmd.encode())
        self.channel.readline()

    def terminate(self):
        self.sock.send(b'{"command": ["quit"]}\n')

    @GObject.Signal(arg_types=())
    def video_loaded(self):
        pass

    @GObject.Signal(arg_types=())
    def video_finished(self):
        pass

    @GObject.Signal(arg_types=(str,))
    def video_loading_failed(self, reason):
        pass


class _MPV(GObject.GObject):

    def __init__(self):
        super().__init__()
        self.__thread = None

    def play_url(self, mpv, url):
        if self.__thread is None:
            self.__thread = _MPVThread(mpv, url)
            self.__thread.connect('video-loaded', \
                lambda *args: self.video_loaded.emit())
            self.__thread.connect('video-finished', \
                lambda *args: self.video_finished.emit())
            self.__thread.connect('video-loading-failed', \
                lambda src, reason: self.video_loading_failed.emit(reason))
            self.__thread.start()
        else:
            self.__thread.replace_url(url)

    def terminate(self):
        if self.__thread is not None:
            self.__thread.terminate()
            self.__thread.join()
            self.__thread = None

    @GObject.Signal(arg_types=())
    def video_loaded(self):
        pass

    @GObject.Signal(arg_types=())
    def video_finished(self):
        self.__thread = None

    @GObject.Signal(arg_types=(str,))
    def video_loading_failed(self, reason):
        self.__thread = None


MPV = _MPV()
