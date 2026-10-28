"""HTTP validation and real queued cancellation without GPU computation."""
import json
import uuid
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts' / 'local-influencer'
API = 'http://127.0.0.1:8000'
raw = (OUT / 'reference.png').read_bytes()
checks = []
for payload, mime, params, expected in [
    (b'invalid image', 'image/png', {}, 400),
    (raw, 'text/plain', {}, 415),
    (raw, 'image/png', {'seed': -1}, 400),
    (raw, 'image/png', {'identity_strength': 5}, 400),
    (raw, 'image/png', {'steps': 100}, 400),
    (raw, 'image/png', {'preset': 'fake'}, 400),
    (raw, 'image/png', {'request_key': 'invalid'}, 400),
]:
    form = {'request_key': str(uuid.uuid4()), **params}
    response = requests.post(API + '/influencer/generations', files={'file': ('test.png', payload, mime)}, data=form, timeout=20)
    assert response.status_code == expected, (expected, response.status_code, response.text)
    checks.append({'parameters': params, 'mime': mime, 'expected': expected, 'passed': True})
response = requests.post(API + '/influencer/generations', files={'file': ('cancellation-test.png', raw, 'image/png')},
    data={'request_key': str(uuid.uuid4()), 'steps': 12}, timeout=20)
response.raise_for_status()
job = response.json()
response = requests.post(API + '/influencer/generations/' + job['id'] + '/cancel', timeout=10)
response.raise_for_status()
assert response.json()['status'] == 'cancelled', response.json()
image = requests.get(API + '/image/' + job['id'], params={'kind': 'generations'}, timeout=10)
assert image.status_code == 409
checks.append({'queued_job_id': job['id'], 'cancelled': True, 'no_output': True})
(OUT / 'validation.json').write_text(json.dumps(checks, indent=2))
print('PASS: 7 invalid-input cases + queued cancellation + unfinished-image conflict')
