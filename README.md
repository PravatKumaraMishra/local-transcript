# Caption Desk — local video transcript extractor

React + Vite interface, local Python FastAPI helper, and yt-dlp caption retrieval. No speech-to-text model, paid API, audio processing, cloud hosting, or video download.

## Requirements
- Python 3.10+ (3.12 recommended)
- Node.js 20.19+ or 22.12+ with npm
- Internet for dependency installation and caption retrieval

## macOS / Linux
Extract the ZIP. Open a terminal in the extracted `local-transcript` folder:

```bash
bash setup.sh
bash Start.command
```

After setup, macOS users can double-click `Start.command` (you may first need `chmod +x Start.command`). On Linux run `bash Start.command`. The browser opens automatically at http://127.0.0.1:8765.

## Windows
Install Python and Node.js, then double-click `Start.bat`. First launch installs dependencies and builds the interface. Keep the launcher window open. If `py` is unavailable, install Python with its Windows launcher enabled.

## Use
1. Paste an HTTPS link to one video.
2. Click **Fetch English subtitles**. Creator English captions are selected automatically; English platform auto captions are the fallback.
3. The transcript appears directly, with no language picker or second extraction step. If no English track exists, the app explains that.
4. Search or toggle timestamps. Use **Copy text**, **Download TXT**, or **Download SRT**. Video chapter titles, when supplied by the platform, appear in the transcript and exports.
5. **Stop** disables extraction and kills an active extraction worker. **Start** re-enables it.

The lightweight launcher/helper remains running so the browser's Start button can work. A normal browser cannot start a process after the helper has exited. Close the terminal or press Ctrl+C to shut down everything; use the launcher to open it again. Closing the browser tab does not terminate the helper.

## Supported links and limitations
The app accepts YouTube, Vimeo, Reddit, Facebook, Instagram, TikTok, Twitch, X/Twitter and Dailymotion domains. Platform compatibility does NOT guarantee captions: only accessible VTT/SRT caption tracks are supported. Creator captions and platform-generated captions can be retrieved, but this app never generates new captions. Videos without captions return an explanation. Social platforms frequently expose no caption track. Private/login-only videos, anti-bot challenges, region restrictions, rate limiting and changed extractor behavior can prevent retrieval. No cookies or credentials are requested or stored. Playlists are rejected.

The app listens only on loopback, checks the Host header and requires a per-launch token for state-changing requests. It is intended for a trusted personal computer, not deployment on a public server. Caption text is rendered as text. Results stay in browser memory until you export them. yt-dlp may print errors in worker output; the UI reports extraction failures. No FFmpeg is needed for the supported formats.

Rolling platform captions can repeat words across overlapping cues. For automatic captions, repeated text shared by overlapping or immediately adjacent rolling cues is removed. Repetition within a cue or after a pause is preserved. Creator captions only merge exact overlapping duplicates. There is no AI cleanup. SRT always contains timing; TXT and copy follow the timestamp toggle. Search only filters the display, not exports.

## Maintenance
Update the extractor if a platform changes:

macOS/Linux: `.venv/bin/python -m pip install --upgrade 'yt-dlp[default]'`

Windows: `.venv\Scripts\python.exe -m pip install --upgrade "yt-dlp[default]"`

Rebuild UI after editing: `cd frontend` then `npm run build`.

## Development and checks
Backend serves the built React app on one origin. Run `python launcher.py` inside your activated virtual environment. To use Vite's development server, configure a local `/api` proxy to port 8765; the normal launcher does not require a dev server.

```bash
.venv/bin/python -m unittest discover -s tests -v
cd frontend
npm run build
```

See TESTING.md for validation performed on the delivered project.

If Python on macOS reports `CERTIFICATE_VERIFY_FAILED`, use the `Install Certificates.command` provided with a python.org Python installation, then retry. Keep TLS verification enabled. If port 8765 is occupied, close the existing instance or the program using that port.

Caption scans and successful transcripts are cached in memory for ten minutes (up to ten entries each). Extraction reuses scanned metadata instead of repeatedly requesting the video page. Subtitle downloads wait five seconds and retry once after thirty seconds for HTTP 429. Persistent platform rate limits still require waiting before trying again. Restart the launcher after backend changes.
