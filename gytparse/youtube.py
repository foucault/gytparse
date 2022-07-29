from dataclasses import dataclass
import re
import json
import requests
import locale

_ID_EXPR = re.compile(r'\s*window\["ytInitialData"\]\s?=\s?(.*);')
_ID_EXPR2 = re.compile(r'\s*var\sytInitialData\s?=\s?(.*);\s?')
_ID_EXPR3 = re.compile(r'^.*var\sytInitialData\s?=\s?(.*);</script>.*$')
_ID_INNERTUBE = re.compile(r'^.*"INNERTUBE_API_KEY"\s?:\s?"([^"]+).*$')
_YT_WATCH = 'https://www.youtube.com/watch'
_YT_SEARCH = 'https://www.youtube.com/results'
_YT_API = 'https://www.youtube.com/youtubei/v1/search'


def _find_initial_data(text):

    (result, innertube_key) = (None, None)

    for line in text.splitlines():

        if not result:
            match = None
            for expr in [_ID_EXPR, _ID_EXPR2, _ID_EXPR3]:
                match = expr.match(line)
                if match is not None:
                    break

            if match is not None:
                result = json.loads(match.group(1))['contents']

        if not innertube_key:
            match = _ID_INNERTUBE.match(line)

            if match is None:
                continue

            innertubeKey = match.group(1)

        if result and innertube_key:
            break

    return (result, innertubeKey)


def _make_proxy_dict(proxy):
    return {
        "http"  : proxy,
        "https" : proxy,
    }


def yt_token_search(token=None, page_token=None, lang=None, locality=None, proxy=None):

    if ((token, page_token) != (None, None)) and not all((token, page_token)):
        raise Exception("Need token AND page_token for token search")

    if lang is None or locality is None or locality.strip() == "":
        (lang, locality) = locale.getlocale()[0].split('_')
        langcode = "%s-%s" % (lang, locality)
    else:
        langcode = "%s-%s" % (lang, locality)
    acceptLang = '%s,%s;q=0.5' % (langcode, lang)

    data = {
        'context': {
            'client': {
                'clientName': 'WEB',
                'clientVersion': '2.20201129.08.00',
                'hl': lang,
                'gl': locality
            }
        },
        'continuation': page_token
    }

    params = { 'key': token }
    headers = {'Accept-Language': acceptLang}

    if proxy is None:
        resp = requests.post(_YT_API, params=params, json=data, headers=headers)
    else:
        resp = requests.post(_YT_API, params=params, json=data, headers=headers,
            proxies=_make_proxy_dict(proxy))

    if not resp.ok:
        raise Exception("Search failed; error: %d" % resp.status_code)

    rawdata = json.loads(resp.content.decode())
    sections = (rawdata['onResponseReceivedCommands'][0]
        ['appendContinuationItemsAction']['continuationItems'])
    continuation = (sections[1]['continuationItemRenderer']
        ['continuationEndpoint']['continuationCommand']['token'])

    return (sections, token, continuation)


def yt_search(query, page=1, lang=None, locality=None, proxy=None):
    if lang is None or locality is None or locality.strip() == "":
        (lang, locality) = locale.getlocale()[0].split('_')
        langcode = "%s-%s" % (lang, locality)
    else:
        langcode = "%s-%s" % (lang, locality)
    acceptLang = '%s,%s;q=0.5' % (langcode, lang)

    params = {'q': query, 'page': page}
    headers = {'Accept-Language': acceptLang}

    if proxy is None:
        resp = requests.get(_YT_SEARCH, params=params, headers=headers)
    else:
        resp = requests.get(_YT_SEARCH, params=params, headers=headers,
            proxies=_make_proxy_dict(proxy))

    if not resp.ok:
        raise Exception("Search failed; error: %d" % resp.status_code)

    (rawdata, apikey) = _find_initial_data(resp.content.decode())
    sections = (rawdata['twoColumnSearchResultsRenderer']
        ['primaryContents']['sectionListRenderer']['contents'])

    continuation = None

    for s in sections:
        try:
            continuation = (s['continuationItemRenderer']
                ['continuationEndpoint']['continuationCommand']['token'])
            break
        except KeyError:
            continue


    return (sections, apikey, continuation)


def yt_playlist(vid, pid, lang=None, locality=None, proxy=None):
    if locality is None or locality.strip() == "":
        langcode = lang
    else:
        langcode = "%s-%s" % (lang, locality)
    acceptLang = '%s,%s;q=0.5' % (langcode, lang)

    params = {'v': vid, 'list': pid}
    headers = {'Accept-Language': acceptLang}

    if proxy is None:
        resp = requests.get(_YT_WATCH, params=params, headers=headers)
    else:
        resp = requests.get(_YT_WATCH, params=params, headers=headers,
            proxies=_make_proxy_dict(proxy))

    if not resp.ok:
        raise Exception("Load playlist failed; error: %d" % resp.status_code)

    rawdata = _find_initial_data(resp.content.decode())[0]
    playlist = (rawdata['twoColumnWatchNextResults']
        ['playlist']['playlist']['contents'])

    return playlist


@dataclass
class Video:
    title: str = ""
    videoId: str = ""
    thumbnail: str = None
    uploader: str = None
    views: str = "0"
    uploaded: str = ""
    duration: str = "00:00"
    snippet: str = ""

    @staticmethod
    def from_dict(data, render_unavailables=False):

        unavailable = False

        if 'unplayableText' in data.keys():
            if not render_unavailables:
                return None
            title = data['unplayableText']['simpleText']
            unavailable = True
        else:
            try:
                title = data['title']['runs'][0]['text']
            except KeyError:
                title = data['title']['simpleText']

        thumb = data['thumbnail']['thumbnails'][0]['url']
        vid = data['videoId']

        try:
            uploader = data['longBylineText']['runs'][0]['text']
        except (KeyError, IndexError):
            uploader = None

        try:
            duration = data['lengthText']['simpleText']
        except KeyError:
            if not unavailable:
                duration = "Live!"
            else:
                duration = "00:00"

        try:
            views = data['viewCountText']['simpleText']
            views = views.split(" ")[0]
        except (KeyError, IndexError):
            views = "0"

        try:
            uploaded = data['publishedTimeText']['simpleText']
        except (KeyError, IndexError):
            uploaded = ""

        try:
            runs = data['detailedMetadataSnippets'][0]['snippetText']['runs']
            snippet = "".join([x['text'] for x in runs])
        except (KeyError, IndexError):
            snippet = ""

        return Video(title=title, videoId=vid, thumbnail=thumb,
            uploader=uploader, views=views, uploaded=uploaded,
            duration=duration, snippet=snippet)


@dataclass
class PlaylistHeader:
    title: str
    playlistId: str
    videoId: str
    uploader: str
    thumbnail: str

    @staticmethod
    def from_playlist_dict(data):
        title = data['title']['simpleText']
        vid = data['navigationEndpoint']['watchEndpoint']['videoId']
        pid = data['navigationEndpoint']['watchEndpoint']['playlistId']
        uploader = data['shortBylineText']['runs'][0]['text']
        thumb = (data['thumbnailRenderer']['playlistVideoThumbnailRenderer']
            ['thumbnail']['thumbnails'][0]['url'])

        return PlaylistHeader(title=title, playlistId=pid, videoId=vid,
            uploader=uploader, thumbnail=thumb)

    @staticmethod
    def from_show_dict(data):
        title = data['title']['simpleText']
        vid = data['navigationEndpoint']['watchEndpoint']['videoId']
        pid = data['navigationEndpoint']['watchEndpoint']['playlistId']
        uploader = data['shortBylineText']['runs'][0]['text']
        thumb = (data['thumbnailRenderer']['showCustomThumbnailRenderer']
            ['thumbnail']['thumbnails'][0]['url'])

        return PlaylistHeader(title=title, playlistId=pid, videoId=vid,
            uploader=uploader, thumbnail=thumb)
