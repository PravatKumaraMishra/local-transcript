import asyncio
import json
import secrets
import sys
import time
from collections import OrderedDict
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .captions import validate_url

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title='Caption Desk')
token = secrets.token_urlsafe(32)
enabled = True
workers = set()
worker_lock = asyncio.Lock()
metadata_cache = OrderedDict()
result_cache = OrderedDict()

def cached(cache, key):
    entry = cache.get(key)
    if entry and time.monotonic() - entry[0] < 600:
        return entry[1]
    cache.pop(key, None)

def remember(cache, key, value):
    cache[key] = (time.monotonic(), value)
    cache.move_to_end(key)
    while len(cache) > 10:
        cache.popitem(last=False)

@app.middleware('http')
async def local_only(request: Request, call_next):
    host = request.headers.get('host', '')
    if host not in ('127.0.0.1:8765', 'localhost:8765', 'testserver'):
        from starlette.responses import JSONResponse
        return JSONResponse({'detail': 'Invalid host'}, status_code=403)
    if request.method == 'POST' and request.headers.get('x-local-token') != token:
        from starlette.responses import JSONResponse
        return JSONResponse({'detail': 'Reload this local page before continuing.'}, status_code=403)
    return await call_next(request)

class Video(BaseModel):
    url: str = Field(max_length=2048)
    language: str = Field(default='en', max_length=100)
    source: str = Field(default='manual', pattern='^(manual|automatic)$')

@app.get('/api/status')
def status():
    return {'running': enabled, 'token': token, 'active': len(workers)}

@app.post('/api/service/{action}')
async def service(action: str):
    global enabled
    if action not in ('start', 'stop'):
        raise HTTPException(400, 'Unknown service action')
    enabled = action == 'start'
    if not enabled:
        for process in list(workers):
            if process.returncode is None:
                process.kill()
    return {'running': enabled}

async def run(action, video):
    if not enabled:
        raise HTTPException(409, 'Start the extraction service first.')
    try:
        validate_url(video.url)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    cache_key = video.url if action == 'inspect' else (video.url, video.language, video.source)
    cache = metadata_cache if action == 'inspect' else result_cache
    hit = cached(cache, cache_key)
    if hit:
        return {k: v for k, v in hit.items() if k != '_info'}
    async with worker_lock:
        if workers:
            raise HTTPException(409, 'Another extraction is running. Wait or stop the service.')
        if not enabled:
            raise HTTPException(409, 'Start the extraction service first.')
        process = await asyncio.create_subprocess_exec(sys.executable, str(ROOT / 'backend/worker.py'), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        workers.add(process)
        if not enabled and process.returncode is None:
            process.kill()
    try:
        request = video.model_dump() | {'action': action}
        metadata = cached(metadata_cache, video.url)
        if action == 'extract' and metadata:
            request['_info'] = metadata['_info']
        out, _ = await asyncio.wait_for(process.communicate(json.dumps(request).encode()), timeout=180)
        if process.returncode != 0:
            raise HTTPException(409, 'Extraction stopped. Start the service and try again.')
        payload = json.loads(out)
        if 'error' in payload:
            raise HTTPException(422, payload['error'])
        result = payload['result']
        remember(cache, cache_key, result)
        return {k: v for k, v in result.items() if k != '_info'}
    except asyncio.TimeoutError:
        raise HTTPException(504, 'The platform took too long. Try again later.')
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(502, 'The caption worker returned an invalid response. Restart the launcher and try again.') from exc
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()
        workers.discard(process)

@app.post('/api/inspect')
async def scan(video: Video):
    return await run('inspect', video)

@app.post('/api/extract')
async def transcript(video: Video):
    return await run('extract', video)

@app.post('/api/english')
async def english(video: Video):
    return await run('english', video)

if (ROOT / 'frontend/dist').exists():
    app.mount('/', StaticFiles(directory=ROOT / 'frontend/dist', html=True), name='frontend')
