import html
import re
import tempfile
import copy
import time
from pathlib import Path
from urllib.parse import urlsplit
import webvtt
import yt_dlp

ALLOWED = ('youtube.com', 'youtu.be', 'vimeo.com', 'reddit.com', 'redd.it', 'facebook.com', 'fb.watch', 'instagram.com', 'tiktok.com', 'dailymotion.com', 'dai.ly', 'twitch.tv', 'twitter.com', 'x.com')

def validate_url(url):
    p = urlsplit(url)
    host = (p.hostname or '').lower()
    if p.scheme != 'https' or p.username or p.password or p.port not in (None, 443) or not any(host == d or host.endswith('.' + d) for d in ALLOWED):
        raise ValueError('Use an HTTPS video link from a supported platform (YouTube, Vimeo, Reddit, Facebook, Instagram, TikTok, Twitch, X or Dailymotion).')
    return url

def options():
    return {'quiet': True, 'no_warnings': True, 'skip_download': True, 'noplaylist': True, 'socket_timeout': 20, 'retries': 0, 'extractor_retries': 1, 'sleep_interval_requests': 1}

def track_priority(track):
    language = track['language'].lower().split('-')[0]
    if track['source'] == 'manual' and language in ('en', 'hi', 'bn'):
        return (0, ('en', 'hi', 'bn').index(language))
    if track['source'] == 'automatic' and language == 'en':
        return (1, 0 if 'orig' in track['language'] else 1)
    return (2, 0)

def chapters(info):
    return [{'start': float(c['start_time']), 'title': c['title']}
            for c in (info.get('chapters') or [])
            if c.get('title') and isinstance(c.get('start_time'), (int, float))]

def inspect(url):
    with yt_dlp.YoutubeDL(options()) as ydl:
        info = ydl.extract_info(validate_url(url), download=False)
        if info:
            info = ydl.sanitize_info(info)
    if not info or info.get('_type') in ('playlist', 'multi_video'):
        raise ValueError('Please use a link to one video, not a playlist.')
    tracks = []
    for source, key in [('manual', 'subtitles'), ('automatic', 'automatic_captions')]:
        for language, formats in (info.get(key) or {}).items():
            if any(f.get('ext') in ('vtt', 'srt') for f in formats):
                tracks.append({'language': language, 'source': source, 'name': next((f.get('name') for f in formats if f.get('name')), language)})
    return info, sorted(tracks, key=track_priority)

def parse_captions(path, automatic=False):
    cues = webvtt.from_srt(str(path)) if path.suffix == '.srt' else webvtt.read(str(path))
    result = []
    previous_words = []
    previous_end = -1
    for cue in cues:
        text = html.unescape(re.sub(r'<[^>]+>', '', cue.text)).strip()
        text = re.sub(r'\s+', ' ', text)
        if not text:
            continue
        def seconds(value):
            h, m, sec = value.replace(',', '.').split(':')
            return int(h) * 3600 + int(m) * 60 + float(sec)
        start, end = seconds(cue.start), seconds(cue.end)
        words = text.split()
        raw_words = words
        # Auto captions roll the previous line into the next cue. Compare raw
        # cues (including skipped ones), so a retained suffix is not repeated.
        if automatic and start <= previous_end + 0.1:
            for count in range(min(len(previous_words), len(words)), 0, -1):
                if previous_words[-count:] == words[:count] and (count >= 2 or count == len(words)):
                    words = words[count:]
                    break
        previous_words, previous_end = raw_words, end
        if not words:
            if result:
                result[-1]['end'] = max(result[-1]['end'], end)
            continue
        text = ' '.join(words)
        if result and text == result[-1]['text'] and start <= result[-1]['end']:
            result[-1]['end'] = max(result[-1]['end'], end)
        else:
            result.append({'start': start, 'end': end, 'text': text})
    if not result:
        raise ValueError('The caption file was empty.')
    return result

def extract(url, language, source, info=None):
    validate_url(url)
    if info is None:
        info, _ = inspect(url)
    key = 'subtitles' if source == 'manual' else 'automatic_captions'
    if language not in (info.get(key) or {}):
        raise ValueError('That caption track is unavailable. Scan the link again.')
    with tempfile.TemporaryDirectory() as folder:
        opts = options() | {'writesubtitles': source == 'manual', 'writeautomaticsub': source == 'automatic', 'subtitleslangs': [re.escape(language)], 'subtitlesformat': 'vtt/srt', 'sleep_interval_subtitles': 5, 'outtmpl': str(Path(folder) / 'captions.%(ext)s')}
        for attempt in range(2):
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.process_ie_result(copy.deepcopy(info), download=True)
                break
            except yt_dlp.utils.DownloadError as exc:
                if '429' not in str(exc) and 'Too Many Requests' not in str(exc):
                    raise
                if attempt:
                    raise ValueError('The platform is still rate limiting captions after a delayed retry. Wait a few minutes before trying again.') from exc
                time.sleep(30)
        files = list(Path(folder).glob('*.vtt')) + list(Path(folder).glob('*.srt'))
        if not files:
            raise ValueError('The platform did not provide a downloadable caption file.')
        return {'title': info.get('title', 'Transcript'), 'language': language, 'source': source, 'segments': parse_captions(files[0], automatic=source == 'automatic'), 'chapters': chapters(info)}


def english_track(tracks):
    english = [t for t in tracks if t['language'].lower().split('-')[0] == 'en']
    if not english:
        raise ValueError('No English subtitles are available for this video, including platform auto captions.')
    return min(english, key=track_priority)
