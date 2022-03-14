import urllib
from types import MethodType
from gi.repository import Gio, Secret


PROXY_PW_SCHEMA = Secret.Schema.new("gr.oscillate.gytparse",
    Secret.SchemaFlags.NONE,
    {"username": Secret.SchemaAttributeType.STRING})


def __current_proxy_url(slf):
    proxy_type = slf.get_string('proxy-type')

    if proxy_type == 'none':
        return None

    proxy_host = slf.get_string('proxy-host').encode('idna').decode()
    proxy_port = slf.get_int('proxy-port')

    if not slf.get_boolean('enable-proxy-auth'):
        return "%s://%s:%d/" % (proxy_type, proxy_host, proxy_port)
    else:
        user = slf.get_string('proxy-auth-username')
        pw = Secret.password_lookup_sync(PROXY_PW_SCHEMA, {"username": user}, None)
        return "%s://%s@%s:%s:%d/" % (proxy_type, user, pw, proxy_host, proxy_port)


def __make_settings(resource='gr.oscillate.gytparse'):
    settings = Gio.Settings.new(resource)
    settings.proxy_url = MethodType(__current_proxy_url, settings)

    return settings


Settings = __make_settings('gr.oscillate.gytparse')
