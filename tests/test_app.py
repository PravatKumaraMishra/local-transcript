import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from backend import app as module
from backend.captions import validate_url, parse_captions, inspect, extract, track_priority, english_track
import yt_dlp

class CaptionsTest(unittest.TestCase):
    def test_preference(self):
        tracks = [{'language': lang, 'source': source} for lang, source in
                  [('fr', 'manual'), ('en', 'automatic'), ('bn', 'manual'), ('hi', 'manual'), ('en-US', 'manual')]]
        self.assertEqual([t['language'] for t in sorted(tracks, key=track_priority)], ['en-US', 'hi', 'bn', 'en', 'fr'])

    def test_extract_cached_metadata_and_chapters(self):
        info = {'id': 'test', 'title': 'Sample', 'ext': 'mp4', 'extractor': 'generic',
                'extractor_key': 'Generic', 'webpage_url': 'https://youtu.be/test',
                'url': 'https://example.com/video.mp4',
                'chapters': [{'start_time': 0, 'end_time': 10, 'title': 'Introduction'}],
                'subtitles': {'en': [{'ext': 'vtt', 'data': 'WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello\n'}]}}
        with patch('backend.captions.inspect') as scan:
            result = extract('https://youtu.be/test', 'en', 'manual', info)
        scan.assert_not_called()
        self.assertEqual(result['segments'][0]['text'], 'Hello')
        self.assertEqual(result['chapters'], [{'start': 0.0, 'title': 'Introduction'}])

    def test_rate_limit_retry_is_bounded(self):
        info = {'subtitles': {'en': [{'ext': 'vtt'}]}}
        with patch('backend.captions.yt_dlp.YoutubeDL') as ydl, patch('backend.captions.time.sleep') as sleep:
            process = ydl.return_value.__enter__.return_value.process_ie_result
            process.side_effect = yt_dlp.utils.DownloadError('HTTP Error 429: Too Many Requests')
            with self.assertRaisesRegex(ValueError, 'still rate limiting'):
                extract('https://youtu.be/test', 'en', 'manual', info)
            self.assertEqual(process.call_count, 2)
            sleep.assert_called_once_with(30)
    def test_english_only_selection(self):
        tracks = [{'language': 'hi', 'source': 'manual'}, {'language': 'en', 'source': 'automatic'}, {'language': 'en-GB', 'source': 'manual'}]
        self.assertEqual(english_track(tracks)['language'], 'en-GB')
        self.assertEqual(english_track(tracks[:2])['source'], 'automatic')
        with self.assertRaisesRegex(ValueError, 'No English subtitles'):
            english_track(tracks[:1])

    def test_urls(self):
        validate_url('https://www.youtube.com/watch?v=abc')
        for url in ['http://youtube.com/a','https://localhost/a','https://youtube.com.evil.org/a','https://user:pass@youtube.com/a','https://youtube.com:99/a']:
            with self.assertRaises(ValueError): validate_url(url)
    def test_vtt_and_overlap(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'a.vtt'
            p.write_text('WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello &amp; <b>world</b>\n\n00:00:02.000 --> 00:00:04.000\nHello &amp; <b>world</b>\n\n00:00:05.000 --> 00:00:06.000\nHello &amp; world\n')
            cues=parse_captions(p)
            self.assertEqual(len(cues),2)
            self.assertEqual(cues[0],{'start':1.0,'end':4.0,'text':'Hello & world'})
    def test_srt(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'a.srt'
            p.write_text('1\n00:00:01,250 --> 00:00:02,500\nTest\n\n')
            self.assertEqual(parse_captions(p)[0]['start'],1.25)
    def test_rolling_auto_captions(self):
        lines = ['all right so in this video I will cover',
                 'all right so in this video I will cover\n60 Linux questions with answers and',
                 '60 Linux questions with answers and',
                 '60 Linux questions with answers and',
                 '60 Linux questions with answers and\nthese questions will be divided into',
                 'these questions will be divided into',
                 'these questions will be divided into\ndifferent categories']
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'rolling.vtt'
            p.write_text('WEBVTT\n\n' + '\n\n'.join(
                f'00:00:{i:02d}.000 --> 00:00:{i+1:02d}.000\n{text}' for i, text in enumerate(lines)))
            cues = parse_captions(p, automatic=True)
            self.assertEqual([c['text'] for c in cues], [lines[0], lines[2], lines[5], 'different categories'])
            self.assertTrue(all(c['end'] > c['start'] for c in cues))

    def test_auto_repetition_after_pause_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'repeat.vtt'
            p.write_text('WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nvery very good\n\n00:00:02.000 --> 00:00:03.000\nvery very good\n')
            self.assertEqual(len(parse_captions(p, automatic=True)), 2)
            self.assertEqual(parse_captions(p, automatic=True)[0]['text'], 'very very good')
    def test_metadata_tracks(self):
        with patch('backend.captions.yt_dlp.YoutubeDL') as mocked:
            mocked.return_value.__enter__.return_value.extract_info.return_value={'title':'Sample','subtitles':{'en':[{'ext':'vtt'}]},'automatic_captions':{'bn':[{'ext':'vtt'}]}}
            mocked.return_value.__enter__.return_value.sanitize_info.side_effect = lambda info: info
            _,tracks=inspect('https://youtu.be/test')
            self.assertEqual([t['source'] for t in tracks],['manual','automatic'])

class APITest(unittest.TestCase):
    def setUp(self):
        module.metadata_cache.clear()
        module.result_cache.clear()
        self.client=TestClient(module.app)
        self.headers={'x-local-token':self.client.get('/api/status').json()['token']}
        module.enabled=True
    def test_control_and_stopped_extraction(self):
        self.assertEqual(self.client.post('/api/service/stop').status_code,403)
        self.assertFalse(self.client.post('/api/service/stop',headers=self.headers).json()['running'])
        self.assertEqual(self.client.post('/api/inspect',headers=self.headers,json={'url':'https://youtu.be/test'}).status_code,409)
        self.assertTrue(self.client.post('/api/service/start',headers=self.headers).json()['running'])
    def test_invalid_url(self):
        response=self.client.post('/api/inspect',headers=self.headers,json={'url':'https://localhost/secret'})
        self.assertEqual(response.status_code,400)
    def test_host(self):
        self.assertEqual(self.client.get('/api/status',headers={'Host':'attacker.example'}).status_code,403)
    def test_cached_scan_hides_internal_metadata(self):
        module.remember(module.metadata_cache, 'https://youtu.be/test', {'title': 'Test', 'tracks': [], '_info': {'private': 'metadata'}})
        response = self.client.post('/api/inspect', headers=self.headers, json={'url': 'https://youtu.be/test'})
        self.assertEqual(response.json(), {'title': 'Test', 'tracks': []})
    def test_malformed_worker_response_is_json_error(self):
        process = MagicMock()
        process.returncode = 0
        process.communicate = AsyncMock(return_value=(b'Internal Server Error', b''))
        process.wait = AsyncMock()
        with patch('backend.app.asyncio.create_subprocess_exec', new=AsyncMock(return_value=process)):
            response = self.client.post('/api/english', headers=self.headers, json={'url': 'https://youtu.be/test'})
        self.assertEqual(response.status_code, 502)
        self.assertIn('invalid response', response.json()['detail'])
        self.assertFalse(module.workers)

    def test_frontend(self):
        self.assertIn('Caption Desk',self.client.get('/').text)
