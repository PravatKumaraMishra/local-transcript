"""Run with the project's virtual environment Python after setup."""
import socket
import threading
import time
import webbrowser
import uvicorn

def open_browser():
    for _ in range(100):
        try:
            with socket.create_connection(('127.0.0.1', 8765), timeout=.2):
                webbrowser.open('http://127.0.0.1:8765')
                return
        except OSError:
            time.sleep(.1)

if __name__ == '__main__':
    from pathlib import Path
    if not (Path(__file__).parent / 'frontend/dist/index.html').exists():
        raise SystemExit('Run setup first. See README.md.')
    threading.Thread(target=open_browser, daemon=True).start()
    print('Caption Desk: http://127.0.0.1:8765 — Ctrl+C closes the launcher.')
    uvicorn.run('backend.app:app', host='127.0.0.1', port=8765)
