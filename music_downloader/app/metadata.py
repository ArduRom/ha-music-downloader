"""
Song metadata lookup against public music libraries.

Queries MusicBrainz, the iTunes Search API and the Deezer API in parallel,
groups the hits that describe the same recording, and derives a "reference"
version of the song (title, artists, album, year, cover, duration). YouTube
search results are then compared against that reference so the UI can show
which videos deviate in length (live versions, remixes, music videos with
intros, ...).

All three services are free and need no API key.
"""
import copy
import re
import statistics
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from urllib.parse import urlparse

import requests

import config

USER_AGENT = "HAMusicDownloader/1.2 ( https://github.com/ArduRom/ha-music-downloader )"
TIMEOUT = 6
CACHE_TTL = 6 * 3600

SOURCE_LABELS = {'itunes': 'iTunes', 'musicbrainz': 'MusicBrainz', 'deezer': 'Deezer'}
# Lower value = preferred when fields disagree
SOURCE_PREF = {'itunes': 0, 'musicbrainz': 1, 'deezer': 2}
COVER_PREF = {'itunes': 0, 'deezer': 1, 'musicbrainz': 2}
# MusicBrainz picks the original (non-compilation) release
ALBUM_PREF = {'musicbrainz': 0, 'itunes': 1, 'deezer': 2}

# Hosts we are willing to download cover art from
COVER_HOSTS = ('mzstatic.com', 'dzcdn.net', 'coverartarchive.org', 'archive.org', 'ytimg.com')

_session = requests.Session()
_session.headers['User-Agent'] = USER_AGENT
_pool = ThreadPoolExecutor(max_workers=6, thread_name_prefix='metadata')


# ---------------------------------------------------------------------------
# Small helpers: cache + rate limiting
# ---------------------------------------------------------------------------

class _TTLCache:
    def __init__(self, ttl, max_items=300):
        self.ttl = ttl
        self.max_items = max_items
        self._data = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            item = self._data.get(key)
            if item and item[0] > time.time():
                return copy.deepcopy(item[1])
            self._data.pop(key, None)
            return None

    def set(self, key, value):
        with self._lock:
            if len(self._data) >= self.max_items:
                oldest = min(self._data, key=lambda k: self._data[k][0])
                self._data.pop(oldest, None)
            self._data[key] = (time.time() + self.ttl, copy.deepcopy(value))


class _RateLimiter:
    """MusicBrainz allows one request per second per client."""

    def __init__(self, interval):
        self.interval = interval
        self._next = 0.0
        self._lock = threading.Lock()

    def wait(self):
        with self._lock:
            now = time.time()
            delay = self._next - now
            self._next = max(now, self._next) + self.interval
        if delay > 0:
            time.sleep(delay)


_cache = _TTLCache(CACHE_TTL)
_mb_limiter = _RateLimiter(1.1)


# ---------------------------------------------------------------------------
# Text normalisation and title parsing
# ---------------------------------------------------------------------------

_JUNK_WORDS = re.compile(
    r"(?i)\b(official|offizielles?|music|musik|video|videoclip|clip|officiel|audio|lyrics?|"
    r"visuali[sz]er|mv|m/v|hd|hq|4k|8k|1080p|720p|explicit|clean|uncensored|full|song|"
    r"version|color coded|subtitulado|legendado|premiere|new)\b"
)
_BRACKETS = re.compile(r"\s*[\(\[\{【「]([^\)\]\}】」]*)[\)\]\}】」]")
_FEAT_PREFIX = re.compile(r"(?i)^\s*(?:feat\.?|ft\.?|featuring|with)\s+(.+)$")
_FEAT_INLINE = re.compile(r"(?i)\s+(?:feat\.?|ft\.?|featuring)\s+(.+?)(?=\s+[-|–—]\s+|$)")
_TRAILING_JUNK = re.compile(
    r"(?i)\s*[-|–—]?\s*\b(official\s+(?:music\s+)?video|official\s+audio|official\s+lyric\s+video|"
    r"lyric\s+video|lyrics|visuali[sz]er|audio|hd|hq|4k)\s*$"
)
_REMASTER = re.compile(
    r"(?i)(\s*[\(\[][^\)\]]*remaster[^\)\]]*[\)\]]|\s+-\s+[^-]*remaster.*$|\s+-\s+(mono|stereo)(\s+version)?$)"
)
_ARTIST_SPLIT = re.compile(
    r"(?i)\s*(?:,|&|\+|\s+x\s+|\s+feat\.?\s+|\s+ft\.?\s+|\s+featuring\s+|\s+vs\.?\s+)\s*"
)
_TITLE_SEPARATORS = (" - ", " – ", " — ", " | ", " ~ ")

# label -> pattern. "variant" flags mark a different recording than the original,
# "info" flags only describe the kind of video.
_FLAG_PATTERNS = [
    ('Live', 'variant', r"\blive\b|\bconcert\b|\bkonzert\b"),
    ('Remix', 'variant', r"\bremix\b|\brmx\b|\bbootleg\b|\bflip\b"),
    ('Extended', 'variant', r"\bextended\b|\bclub mix\b"),
    ('Sped Up', 'variant', r"\bsped\s*up\b|\bspeed\s*up\b"),
    ('Slowed', 'variant', r"\bslowed\b|\breverb\b"),
    ('Nightcore', 'variant', r"\bnightcore\b"),
    ('8D', 'variant', r"\b8d\b"),
    ('Instrumental', 'variant', r"\binstrumental\b"),
    ('Karaoke', 'variant', r"\bkaraoke\b"),
    ('Akustik', 'variant', r"\bacoustic\b|\bakustik\b|\bunplugged\b"),
    ('Cover', 'variant', r"\bcover\b"),
    ('Loop', 'variant', r"\b1 hour\b|\b1 stunde\b|\bloop\b"),
    ('Musikvideo', 'info', r"official\s+(music\s+)?video|musikvideo|videoclip|\bmv\b"),
    ('Lyrics', 'info', r"\blyrics?\b"),
]


def norm(text):
    """Lowercase, strip accents and punctuation for fuzzy comparisons."""
    if not text:
        return ""
    text = unicodedata.normalize('NFKD', str(text))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[\W_]+", " ", text)
    return " ".join(text.split())


def _is_junk(segment):
    rest = _JUNK_WORDS.sub(" ", segment)
    return not re.sub(r"[\W_\d]+", "", rest)


def _dedupe(items):
    seen, out = set(), []
    for item in items:
        item = (item or "").strip()
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def split_artists(text):
    if not text:
        return []
    return _dedupe(_ARTIST_SPLIT.split(text))


def _strip_junk_segments(title):
    """Drop " | Official Audio"-style segments."""
    if " | " not in title:
        return title
    parts = title.split(" | ")
    return parts[0] + "".join(" | " + p for p in parts[1:] if not _is_junk(p))


def clean_title(title):
    """Remove YouTube junk like "(Official Video)" and pull out featured artists.

    Returns (clean_title, featured_artists).
    """
    title = (title or "").strip()
    featured = []

    def _bracket(match):
        content = match.group(1).strip()
        feat = _FEAT_PREFIX.match(content)
        if feat:
            featured.extend(split_artists(feat.group(1)))
            return ""
        if _is_junk(content):
            return ""
        return match.group(0)

    title = _strip_junk_segments(_BRACKETS.sub(_bracket, title))

    inline = _FEAT_INLINE.search(title)
    if inline:
        featured.extend(split_artists(inline.group(1)))
        title = title[:inline.start()] + title[inline.end():]

    for _ in range(3):
        title = _TRAILING_JUNK.sub("", title)

    title = re.sub(r"\s{2,}", " ", title).strip(" -–—|~")
    return title.strip(), _dedupe(featured)


def _clean_channel(channel):
    channel = (channel or "").strip()
    channel = re.sub(r"(?i)\s*-\s*topic$", "", channel)
    channel = re.sub(r"(?i)\s*vevo$", "", channel)
    channel = re.sub(r"(?i)\s*\b(official)\b\s*$", "", channel)
    return channel.strip()


def parse_video_title(title, channel):
    """Best-effort split of a YouTube title into (artists, song_title)."""
    title = _strip_junk_segments((title or "").strip())
    artist_str = _clean_channel(channel)
    song = title

    for sep in _TITLE_SEPARATORS:
        if sep in title:
            left, right = title.split(sep, 1)
            artist_str, song = left.strip(), right.strip()
            break

    song, featured = clean_title(song)
    artists = _dedupe(split_artists(artist_str) + featured)
    return (artists or ["Unknown Artist"]), (song or title)


def detect_flags(text, reference_title=None):
    """Return flags like Live/Remix found in text but not in the reference title."""
    hay = (text or "").lower()
    ref = (reference_title or "").lower()
    flags = []
    for label, kind, pattern in _FLAG_PATTERNS:
        if re.search(pattern, hay) and not re.search(pattern, ref):
            flags.append({'label': label, 'kind': kind})
    return flags


def _compare_title(title):
    clean, _ = clean_title(title)
    return norm(_REMASTER.sub("", clean))


def similarity(a, b):
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    seq = SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    jaccard = len(ta & tb) / len(ta | tb)
    return max(seq, jaccard)


def _containment(needle, haystack):
    """Fraction of needle tokens present in haystack."""
    tn, th = set(norm(needle).split()), set(norm(haystack).split())
    if not tn:
        return 0.0
    return len(tn & th) / len(tn)


def deviation(video_duration, reference_duration):
    """Length difference (video minus reference) and a severity level."""
    if not video_duration or not reference_duration:
        return None
    delta = int(round(float(video_duration) - float(reference_duration)))
    dist = abs(delta)
    if dist <= 3:
        level = 'exact'
    elif dist <= 10:
        level = 'close'
    elif dist <= 30:
        level = 'off'
    else:
        level = 'far'
    return {'delta': delta, 'level': level}


# ---------------------------------------------------------------------------
# Library sources
# ---------------------------------------------------------------------------

def _candidate(source, rank, title, artists, album="", year="", duration=None, cover=None,
               genre="", isrc=None, track_number=None, link=None, mbid=None):
    clean, featured = clean_title(title)
    artists = _dedupe(list(artists or []) + featured)
    return {
        'source': source,
        'rank': rank,
        'title': clean or title,
        'raw_title': title,
        'artists': artists,
        'album': (album or "").strip(),
        'year': (year or "")[:4],
        'duration': round(duration) if duration else None,
        'cover': cover,
        'genre': genre or "",
        'isrc': isrc,
        'track_number': track_number,
        'link': link,
        'mbid': mbid,
    }


def _lucene(text):
    return (text or "").replace("\\", "\\\\").replace('"', '\\"')


def _pick_mb_release(releases):
    def key(rel):
        group = rel.get('release-group') or {}
        return (
            rel.get('status') != 'Official',
            group.get('primary-type') not in ('Album', 'Single', 'EP'),
            bool(group.get('secondary-types')),
            rel.get('date') or '9999',
        )
    return sorted(releases, key=key)[0] if releases else None


def _search_musicbrainz(query, artist=None, title=None, limit=10):
    if artist and title:
        params = {'query': f'recording:"{_lucene(title)}" AND artist:"{_lucene(artist)}"'}
    else:
        params = {'query': query, 'dismax': 'true'}
    params.update({'fmt': 'json', 'limit': limit})

    _mb_limiter.wait()
    resp = _session.get("https://musicbrainz.org/ws/2/recording", params=params, timeout=TIMEOUT)
    resp.raise_for_status()

    out = []
    for rank, rec in enumerate(resp.json().get('recordings') or []):
        if rec.get('video') or (rec.get('score') or 0) < 50:
            continue
        credits = rec.get('artist-credit') or []
        artists = [c.get('name') or (c.get('artist') or {}).get('name') for c in credits]
        release = _pick_mb_release(rec.get('releases') or [])
        album, track_number, cover = "", None, None
        if release:
            album = release.get('title') or ""
            group = release.get('release-group') or {}
            if group.get('id'):
                cover = f"https://coverartarchive.org/release-group/{group['id']}/front-250"
            media = release.get('media') or []
            if media and media[0].get('track'):
                track_number = media[0]['track'][0].get('number')
        tags = sorted(rec.get('tags') or [], key=lambda t: -(t.get('count') or 0))
        out.append(_candidate(
            'musicbrainz', rank,
            title=rec.get('title') or "",
            artists=artists,
            album=album,
            year=rec.get('first-release-date') or (release or {}).get('date') or "",
            duration=(rec.get('length') or 0) / 1000.0 or None,
            cover=cover,
            genre=tags[0]['name'].title() if tags else "",
            isrc=(rec.get('isrcs') or [None])[0],
            track_number=track_number,
            link=f"https://musicbrainz.org/recording/{rec.get('id')}",
            mbid=rec.get('id'),
        ))
    return out


def _itunes_album(collection, title):
    collection = collection or ""
    if re.search(r"(?i)\s+-\s+single$", collection):
        return title
    return re.sub(r"(?i)\s+-\s+(ep)$", "", collection)


def _search_itunes(query, artist=None, title=None, limit=10):
    term = f"{artist} {title}" if artist and title else query
    params = {
        'term': term, 'media': 'music', 'entity': 'song', 'limit': limit,
        'country': getattr(config, 'METADATA_COUNTRY', 'DE') or 'DE',
    }
    resp = _session.get("https://itunes.apple.com/search", params=params, timeout=TIMEOUT)
    resp.raise_for_status()

    out = []
    for rank, track in enumerate(resp.json().get('results') or []):
        if track.get('kind') != 'song':
            continue
        song_title = track.get('trackName') or ""
        cover = track.get('artworkUrl100')
        if cover:
            cover = cover.replace('100x100bb', '600x600bb')
        out.append(_candidate(
            'itunes', rank,
            title=song_title,
            artists=split_artists(track.get('artistName')),
            album=_itunes_album(track.get('collectionName'), clean_title(song_title)[0]),
            year=track.get('releaseDate') or "",
            duration=(track.get('trackTimeMillis') or 0) / 1000.0 or None,
            cover=cover,
            genre=track.get('primaryGenreName') or "",
            track_number=track.get('trackNumber'),
            link=track.get('trackViewUrl'),
        ))
    return out


def _search_deezer(query, artist=None, title=None, limit=10):
    if artist and title:
        q = f'artist:"{artist}" track:"{title}"'
    else:
        q = query
    resp = _session.get("https://api.deezer.com/search", params={'q': q, 'limit': limit}, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    if data.get('error'):
        raise RuntimeError((data['error'] or {}).get('message') or 'Deezer error')

    out = []
    for rank, track in enumerate(data.get('data') or []):
        album = track.get('album') or {}
        out.append(_candidate(
            'deezer', rank,
            title=track.get('title') or "",
            artists=split_artists((track.get('artist') or {}).get('name')),
            album=album.get('title') or "",
            duration=track.get('duration'),
            cover=album.get('cover_xl') or album.get('cover_big'),
            link=track.get('link'),
        ))
    return out


_SOURCES = {
    'musicbrainz': _search_musicbrainz,
    'itunes': _search_itunes,
    'deezer': _search_deezer,
}


def _run_source(name, query, artist, title):
    key = (name, query, artist, title)
    cached = _cache.get(key)
    if cached is not None:
        return cached, None
    try:
        result = _SOURCES[name](query, artist, title)
        _cache.set(key, result)
        return result, None
    except Exception as e:  # network errors, rate limits, bad JSON
        print(f"Metadata source {name} failed: {e}")
        return [], f"{SOURCE_LABELS[name]} nicht erreichbar"


# ---------------------------------------------------------------------------
# Grouping + reference selection
# ---------------------------------------------------------------------------

def _cluster(candidates):
    clusters = []
    for cand in sorted(candidates, key=lambda c: (c['rank'], SOURCE_PREF[c['source']])):
        tkey = _compare_title(cand['title'])
        akey = norm(cand['artists'][0] if cand['artists'] else "")
        for cl in clusters:
            if similarity(tkey, cl['tkey']) < 0.88 or similarity(akey, cl['akey']) < 0.75:
                continue
            durations = [i['duration'] for i in cl['items'] if i['duration']]
            if cand['duration'] and durations and abs(cand['duration'] - statistics.median(durations)) > 12:
                continue
            cl['items'].append(cand)
            break
        else:
            clusters.append({'tkey': tkey, 'akey': akey, 'items': [cand]})
    return clusters


def _relevance(query, artist, title, item):
    if artist and title:
        return 0.6 * similarity(_compare_title(title), _compare_title(item['title'])) + \
            0.4 * similarity(artist, item['artists'][0] if item['artists'] else "")
    text = " ".join(item['artists'][:1] + [item['title']])
    return 0.5 * _containment(text, query) + 0.5 * _containment(query, text)


def _merge(cluster, score, relevance):
    items = cluster['items']
    pref = sorted(items, key=lambda i: (SOURCE_PREF[i['source']], i['rank']))

    mb_items = [i for i in pref if i['source'] == 'musicbrainz' and i['artists']]
    artists = mb_items[0]['artists'] if mb_items else max(pref, key=lambda i: len(i['artists']))['artists']

    dated = [i for i in items if i['year']]
    album_src = min(dated, key=lambda i: (i['year'], ALBUM_PREF[i['source']])) if dated else pref[0]
    album = album_src['album'] or next((i['album'] for i in pref if i['album']), "")

    durations = [i['duration'] for i in items if i['duration']]
    covers = sorted((i for i in items if i['cover']), key=lambda i: COVER_PREF[i['source']])
    genre = next((i['genre'] for i in pref if i['genre']), "")

    sources, seen = [], set()
    for item in pref:
        if item['source'] in seen:
            continue
        seen.add(item['source'])
        sources.append({
            'source': item['source'],
            'label': SOURCE_LABELS[item['source']],
            'duration': item['duration'],
            'link': item['link'],
        })

    return {
        'title': pref[0]['title'],
        'artists': artists,
        'artist': ", ".join(artists),
        'album': album or pref[0]['title'],
        'year': album_src['year'] if dated else "",
        'duration': int(round(statistics.median(durations))) if durations else None,
        'cover': covers[0]['cover'] if covers else None,
        'genre': genre,
        'isrc': next((i['isrc'] for i in items if i['isrc']), None),
        'track_number': album_src.get('track_number'),
        'mbid': next((i['mbid'] for i in items if i['mbid']), None),
        'sources': sources,
        'confidence': round(min(1.0, 0.55 * len(sources) / 3.0 + 0.45 * relevance), 2),
        'score': round(score, 3),
    }


def lookup(query=None, artist=None, title=None, max_matches=8):
    """Search all libraries and return merged matches, best first.

    Returns {'matches': [...], 'reference': match or None, 'errors': [...]}.
    """
    query = (query or "").strip() or f"{artist or ''} {title or ''}".strip()
    if not query:
        return {'matches': [], 'reference': None, 'errors': []}

    cache_key = ('lookup', query, artist, title)
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    futures = [_pool.submit(_run_source, name, query, artist, title) for name in _SOURCES]
    candidates, errors = [], []
    for fut in futures:
        result, error = fut.result()
        candidates.extend(result)
        if error:
            errors.append(error)

    query_text = query if not (artist and title) else f"{artist} {title}"
    scored = []
    for cl in _cluster(candidates):
        rel = max(_relevance(query, artist, title, item) for item in cl['items'])
        n_sources = len({i['source'] for i in cl['items']})
        best_rank = min(i['rank'] for i in cl['items'])
        penalty = 1.5 * len([f for f in detect_flags(cl['items'][0]['raw_title'], query_text)
                             if f['kind'] == 'variant'])
        score = n_sources + 2.5 * rel + 1.0 / (1 + best_rank) - penalty
        scored.append(_merge(cl, score, rel))

    scored.sort(key=lambda m: -m['score'])
    matches = scored[:max_matches]
    result = {'matches': matches, 'reference': matches[0] if matches else None, 'errors': errors}
    if not errors:
        _cache.set(cache_key, result)
    return result


def suggest(query, limit=6):
    """Fast type-ahead suggestions (Deezer, falling back to iTunes)."""
    query = (query or "").strip()
    if len(query) < 2:
        return []
    for name in ('deezer', 'itunes'):
        items, error = _run_source(name, query, None, None)
        if error or not items:
            continue
        out = []
        for item in items[:limit]:
            out.append(_merge({'items': [item]}, 0, 1.0))
        return out
    return []


def match_reference(reference, matches):
    """Find the library match describing the same recording as a pinned reference."""
    if not reference:
        return None
    for match in matches:
        if similarity(_compare_title(match['title']), _compare_title(reference.get('title'))) < 0.88:
            continue
        if similarity((match['artists'] or [""])[0], (reference.get('artists') or [""])[0]) < 0.75:
            continue
        dev = deviation(match.get('duration'), reference.get('duration'))
        if dev and dev['level'] not in ('exact', 'close'):
            continue
        merged = dict(match)
        if reference.get('duration'):
            merged['duration'] = reference['duration']
        return merged
    return reference


# ---------------------------------------------------------------------------
# Comparing YouTube videos with the reference
# ---------------------------------------------------------------------------

def compare_video(video, reference):
    title = video.get('title') or ""
    channel = video.get('channel') or ""
    is_topic = bool(re.search(r"(?i)-\s*topic$", channel))
    official = is_topic or 'vevo' in channel.lower() or bool(video.get('verified'))

    info = {
        'official': official,
        'topic': is_topic,
        'flags': detect_flags(title, reference.get('title') if reference else None),
        'deviation': None,
        'related': None,
        'score': 0.0,
    }
    if not reference:
        return info

    ref_artist = (reference.get('artists') or [""])[0]
    _, song = parse_video_title(title, channel)
    title_part = _containment(_compare_title(reference.get('title')), title)
    title_part *= 0.6 + 0.4 * similarity(_compare_title(song), _compare_title(reference.get('title')))
    artist_part = _containment(ref_artist, f"{title} {_clean_channel(channel)}")
    related = round(0.7 * title_part + 0.3 * artist_part, 2)

    dev = deviation(video.get('duration'), reference.get('duration'))
    info['related'] = related
    info['deviation'] = dev if related >= 0.5 else None

    level_score = {'exact': 3.0, 'close': 2.0, 'off': 0.5, 'far': -1.0}
    score = 3.0 * related
    if info['deviation']:
        score += level_score[info['deviation']['level']]
    score -= 2.0 * len([f for f in info['flags'] if f['kind'] == 'variant'])
    score += 1.5 if is_topic else (1.0 if official else 0.0)
    info['score'] = round(score, 2)
    return info


def annotate_videos(videos, reference):
    for video in videos:
        video['match'] = compare_video(video, reference)
        video['recommended'] = False
    if reference and videos:
        best = max(videos, key=lambda v: v['match']['score'])
        if best['match']['deviation'] and best['match']['deviation']['level'] in ('exact', 'close'):
            best['recommended'] = True
    return videos


def choose_for_video(matches, artist, title, duration):
    """Pick the library match that best fits a specific video.

    Returns (match_index or None, confident).
    """
    best_idx, best_score, best_conf = None, None, False
    level_bonus = {'exact': 1.5, 'close': 1.0, 'off': 0.3, 'far': -0.5}
    for idx, match in enumerate(matches):
        t_sim = similarity(_compare_title(title), _compare_title(match['title']))
        a_sim = max([similarity(artist, a) for a in match['artists']] or [0.0])
        dev = deviation(duration, match.get('duration'))
        score = 2.0 * t_sim + a_sim + (level_bonus[dev['level']] if dev else 0) + 0.2 * match['confidence']
        if best_score is None or score > best_score:
            best_idx, best_score = idx, score
            best_conf = t_sim >= 0.75 and a_sim >= 0.5
    return best_idx, best_conf


def is_allowed_cover_url(url):
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    host = (parsed.hostname or "").lower()
    return parsed.scheme == 'https' and any(host == h or host.endswith('.' + h) for h in COVER_HOSTS)


def fetch_cover(url):
    """Download cover art. Returns (bytes, mime) or (None, None)."""
    if not url or not is_allowed_cover_url(url):
        return None, None
    try:
        resp = _session.get(url, timeout=10)
        resp.raise_for_status()
        mime = resp.headers.get('Content-Type', 'image/jpeg').split(';')[0].strip()
        if not mime.startswith('image/'):
            return None, None
        return resp.content, mime
    except Exception as e:
        print(f"Cover download failed ({url}): {e}")
        return None, None
