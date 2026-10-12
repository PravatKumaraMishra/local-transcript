import contextlib
import json
import sys
from captions import inspect, extract, chapters, english_track

try:
    request = json.load(sys.stdin)
    # Keep stdout exclusively for the JSON protocol, including extractor messages.
    with contextlib.redirect_stdout(sys.stderr):
        if request['action'] == 'inspect':
            info, tracks = inspect(request['url'])
            result = {'title': info.get('title', 'Video'), 'tracks': tracks, 'chapters': chapters(info), '_info': info}
        elif request['action'] == 'english':
            info, tracks = inspect(request['url'])
            track = english_track(tracks)
            result = extract(request['url'], track['language'], track['source'], info)
        else:
            result = extract(request['url'], request['language'], request['source'], request.get('_info'))
    output = json.dumps({'result': result})
except Exception as exc:
    output = json.dumps({'error': str(exc)[-1800:]})
print(output)
