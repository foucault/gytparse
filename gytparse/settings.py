import urllib
from types import MethodType
from gi.repository import Gio


def __current_proxy_url(slf):
    proxy_type = slf.get_string('proxy-type')

    if proxy_type == 'none':
        return None

    proxy_host = slf.get_string('proxy-host').encode('idna').decode()
    proxy_port = slf.get_int('proxy-port')

    return "%s://%s:%d" % (proxy_type, proxy_host, proxy_port)


def __make_settings(resource='gr.oscillate.gytparse'):
    settings = Gio.Settings.new(resource)
    settings.proxy_url = MethodType(__current_proxy_url, settings)

    return settings


Settings = __make_settings('gr.oscillate.gytparse')
