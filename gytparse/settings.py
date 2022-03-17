import os
import urllib
from types import MethodType
from gi.repository import Gio


CHOICE_TO_NAME = {
    'best': _('best'),
    'automatic': _('automatic'),
    'none': _('none')
}

NAME_TO_CHOICE = dict([reversed(i) for i in CHOICE_TO_NAME.items()])


class _KDERetriever:

    def __init__(self):
        import dbus
        self.appid = 'gr.oscillate.gytparse'
        self.bus = dbus.SessionBus()
        self.iface = dbus.Interface(\
            self.bus.get_object('org.kde.kwalletd5', '/modules/kwalletd5'),\
            dbus_interface='org.kde.KWallet')
        self.wallet = self.iface.networkWallet()
        self.walletid = self.iface.open(self.wallet, 0, self.appid)
        self.iface.createFolder(self.walletid, self.appid, self.appid)

    def get(self, uname):
        pw = self.iface.readPassword(self.walletid, self.appid, uname, self.appid)
        if pw == '':
            return None
        return pw

    def set(self, uname, pw):
        self.iface.writePassword(self.walletid, self.appid, uname, pw, self.appid)


class _LibSecretRetriever:

    def __init__(self):
        import gi
        gi.require_version("Secret", "1")
        from gi.repository import Secret

        self.libsecret = Secret
        self.PROXY_PW_SCHEMA = Secret.Schema.new("gr.oscillate.gytparse",
            Secret.SchemaFlags.NONE,
            {"username": Secret.SchemaAttributeType.STRING})

    def get(self, uname):
        pw = self.libsecret.password_lookup_sync(self.PROXY_PW_SCHEMA, \
            {"username": uname}, None)
        return pw

    def set(self, uname, pw):
        self.libsecret.password_store(self.PROXY_PW_SCHEMA,\
            {"username": uname}, \
            self.libsecret.COLLECTION_DEFAULT, \
            "Proxy authentication password", pw, None, \
            lambda _, p: self.libsecret.password_store_finish(p))


class _Secrets:

    def __init__(self):
        de = os.environ.get('XDG_CURRENT_DESKTOP', None)

        if de is None:
            raise ValueError("Unknown desktop environment")

        if de == 'KDE':
            self.retriever = _KDERetriever()
        else:
            self.retriever = _LibSecretRetriever()

    def get(self, uname):
        return self.retriever.get(uname)

    def set(self, uname, pw):
        self.retriever.set(uname, pw)


Secrets = _Secrets()


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
        pw = Secrets.get(user)
        return "%s://%s@%s:%s:%d/" % (proxy_type, user, pw, proxy_host, proxy_port)


def __get_i18n_string(slf, key):
    value = Settings.get_string(key)
    return CHOICE_TO_NAME.get(value, value)


def __set_i18n_string(slf, key, value):
    actual_value = NAME_TO_CHOICE.get(value, value)
    Settings.set_string(key, actual_value)


def __make_settings(resource='gr.oscillate.gytparse'):
    settings = Gio.Settings.new(resource)
    settings.proxy_url = MethodType(__current_proxy_url, settings)
    settings.get_i18n_string = MethodType(__get_i18n_string, settings)
    settings.set_i18n_string = MethodType(__set_i18n_string, settings)

    return settings


Settings = __make_settings('gr.oscillate.gytparse')
