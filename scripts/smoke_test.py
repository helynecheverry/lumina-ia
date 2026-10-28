"""Real GPU + MongoDB integration checks; writes reviewable image artifacts."""
import base64
import io
import json
from pathlib import Path
import requests
from PIL import Image
from skimage import data
from pymongo import MongoClient
from bson import ObjectId
from gridfs import GridFS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts'
OUT.mkdir(exist_ok=True)
API = 'http://127.0.0.1:8000'
report = {'health': requests.get(API + '/health', timeout=10).json(), 'restorations': [], 'checks': []}
assert report['health']['mongodb'] == 'ok'
from dotenv import load_dotenv
import os
load_dotenv(ROOT / '.env')
db = MongoClient(os.getenv('MONGO_URI'))[os.getenv('MONGO_DB', 'face_restoration')]

for name, source in [('portrait', data.astronaut()), ('photograph', data.rocket())]:
    original = Image.fromarray(source).convert('RGB')
    original.thumbnail((128, 128))
    stream = io.BytesIO()
    original.save(stream, 'JPEG', quality=55)
    raw = stream.getvalue()
    (OUT / f'{name}_input.jpg').write_bytes(raw)
    r = requests.post(API + '/restore', files={'file': (name + '.jpg', raw, 'image/jpeg')}, data={'scale': 2}, timeout=180)
    r.raise_for_status()
    result = r.json()
    output = base64.b64decode(result.pop('image_base64'))
    assert Image.open(io.BytesIO(output)).size == (original.width * 2, original.height * 2)
    doc = db.jobs.find_one({'_id': ObjectId(result['id'])})
    assert doc and GridFS(db).get(doc['gridfs_id']).read() == output
    stored = requests.get(API + '/image/' + result['id'], timeout=10)
    assert stored.content == output
    (OUT / f'{name}_restored.png').write_bytes(output)
    before = original.resize((original.width * 2, original.height * 2))
    comparison = Image.new('RGB', (before.width * 2, before.height))
    comparison.paste(before, (0, 0))
    comparison.paste(Image.open(io.BytesIO(output)), (before.width, 0))
    comparison.save(OUT / f'{name}_comparison.png')
    report['restorations'].append(dict(name=name, **result))

for effect in ('sketch', 'edges', 'denoise'):
    r = requests.post(API + '/edit', files={'file': ('portrait.jpg', raw, 'image/jpeg')}, data={'filter_name': effect}, timeout=60)
    r.raise_for_status()
    result = r.json()
    output = base64.b64decode(result['image_base64'])
    assert result['saved']
    assert db.edits.find_one({'_id': ObjectId(result['id'])})
    assert requests.get(API + '/image/' + result['id'], params={'kind': 'edits'}, timeout=10).content == output
    (OUT / f'{effect}.png').write_bytes(output)
    report['checks'].append(effect + ': MongoDB + GridFS + retrieval OK')

for path, files, form, expected in [
    ('/restore', {'file': ('bad.png', b'bad', 'image/png')}, {}, 400),
    ('/restore', {'file': ('photo.jpg', raw, 'image/jpeg')}, {'scale': 9}, 400),
    ('/edit', {'file': ('bad.txt', b'bad', 'text/plain')}, {}, 415),
    ('/edit', {'file': ('bad.png', b'bad', 'image/png')}, {}, 400),
    ('/edit', {'file': ('photo.jpg', raw, 'image/jpeg')}, {'filter_name': 'invalid'}, 400),
]:
    response = requests.post(API + path, files=files, data=form, timeout=20)
    assert response.status_code == expected, response.text
    report['checks'].append(f'{path}: invalid input → {expected}')
assert requests.get(API + '/image/invalid', timeout=10).status_code == 400
assert requests.get(API + '/image/000000000000000000000000', timeout=10).status_code == 404
assert requests.get(API + '/history', timeout=10).ok
assert requests.get(API + '/history', params={'kind': 'edits'}, timeout=10).ok
report['checks'].append('history + invalid/missing IDs OK')
# Negative brightness must clip, not reflect negative values to positive.
black = io.BytesIO()
Image.new('RGB', (4,4)).save(black, 'PNG')
r = requests.post(API + '/edit', files={'file': ('black.png', black.getvalue(), 'image/png')}, data={'brightness': -50, 'save_result': 'false'}, timeout=20)
r.raise_for_status()
assert max(Image.open(io.BytesIO(base64.b64decode(r.json()['image_base64']))).getextrema()[0]) == 0
report['checks'].append('negative brightness clips to black OK')
(OUT / 'test_report.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
