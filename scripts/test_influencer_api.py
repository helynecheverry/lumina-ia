"""Exercise the real offline generator through the API and verify GridFS output."""
import io
import json
import os
import sys
import time
import uuid
from pathlib import Path

import requests
from PIL import Image
from skimage import data
from pymongo import MongoClient
from bson import ObjectId
from gridfs import GridFS
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
OUT = ROOT / 'artifacts' / 'local-influencer'
OUT.mkdir(parents=True, exist_ok=True)
API = 'http://127.0.0.1:8000'
config = requests.get(API + '/influencer/config', timeout=10).json()
assert config['ready'], config
buf = io.BytesIO(); Image.fromarray(data.astronaut()).save(buf, 'PNG')
raw = buf.getvalue()
(OUT / 'reference.png').write_bytes(raw)
request_key = str(uuid.uuid4())
params = {'preset': sys.argv[1] if len(sys.argv) > 1 else 'cinema', 'seed': 9241, 'steps': 20, 'request_key': request_key}
if params['preset'] == 'illustration':
    params['identity_strength'] = .5
response = requests.post(API + '/influencer/generations', files={'file': ('portrait.png', raw, 'image/png')}, data=params, timeout=30)
response.raise_for_status()
job = response.json()
(OUT / 'last_job.json').write_text(json.dumps(job, indent=2))
print('Job:', job['id'], flush=True)
# Idempotent repeat must not create a second queued request.
repeat = requests.post(API + '/influencer/generations', files={'file': ('portrait.png', raw, 'image/png')}, data=params, timeout=30)
repeat.raise_for_status(); assert repeat.json()['id'] == job['id']
last_progress = None
start = time.monotonic()
while time.monotonic() - start < 900:
    status = requests.get(API + '/influencer/generations/' + job['id'], timeout=15)
    status.raise_for_status(); job = status.json()
    if job['progress'] != last_progress or job['status'] not in ('queued', 'processing'):
        print(job['status'], job['progress'], job['message'], flush=True)
        last_progress = job['progress']
    if job['status'] not in ('queued', 'processing'):
        break
    time.sleep(3)
assert job['status'] == 'completed', job
output = requests.get(API + '/image/' + job['id'], params={'kind': 'generations'}, timeout=30)
output.raise_for_status()
image = Image.open(io.BytesIO(output.content))
assert image.size == (512, 512)
assert image.convert('L').getextrema()[1] > 10
reference = requests.get(API + '/influencer/generations/' + job['id'] + '/reference', timeout=10)
assert Image.open(io.BytesIO(reference.content)).size == (512, 512)
db = MongoClient(os.getenv('MONGO_URI'))[os.getenv('MONGO_DB', 'face_restoration')]
doc = db.generations.find_one({'_id': ObjectId(job['id'])})
assert doc['status'] == 'completed'
assert GridFS(db).get(doc['gridfs_id']).read() == output.content
(OUT / (params['preset'] + '.png')).write_bytes(output.content)
(OUT / (params['preset'] + '.json')).write_text(json.dumps(job, indent=2))
comparison = Image.new('RGB', (1024, 512))
comparison.paste(Image.open(io.BytesIO(raw)), (0, 0))
comparison.paste(image, (512, 0))
comparison.save(OUT / (params['preset'] + '_comparison.png'))
assets = ROOT / 'app' / 'assets' / 'portraits'; assets.mkdir(parents=True, exist_ok=True)
(assets / (params['preset'] + '.png')).write_bytes(output.content)
print('PASS: GPU generation + idempotency + API + MongoDB/GridFS + download', flush=True)
print(json.dumps(job, indent=2), flush=True)
