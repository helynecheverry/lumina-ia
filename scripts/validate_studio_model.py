"""End-to-end local API test with real inference and MongoDB persistence."""
import argparse
import hashlib
import io
import json
import sys
import time
import uuid
from pathlib import Path

import requests
from PIL import Image, ImageStat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def validate(model_id, framing, steps):
    from app.model_registry import MODELS
    folder = ROOT/'artifacts/multi-model'
    folder.mkdir(parents=True, exist_ok=True)
    raw = (ROOT/'web/assets/demo-reference.jpg').read_bytes()
    response = requests.post('http://127.0.0.1:8000/influencer/generations',
        files={'file': ('public-reference.jpg', raw, 'image/jpeg')},
        data=dict(model_id=model_id, framing=framing, preset='professional', character_type='natural',
                  prompt='tailored black blazer, elegant editorial photography, soft window lighting',
                  steps=steps, seed=42817, identity_strength=.65, request_key=str(uuid.uuid4())), timeout=30)
    response.raise_for_status()
    job_id = response.json()['id']
    print('JOB', job_id, flush=True)
    previous = None
    deadline = time.monotonic()+3600
    while time.monotonic() < deadline:
        result = requests.get(f'http://127.0.0.1:8000/influencer/generations/{job_id}', timeout=20).json()
        marker = (result['status'], result['progress'], result['message'])
        if marker != previous:
            print(marker, flush=True)
            previous = marker
        if result['status'] not in ('queued', 'processing'):
            break
        time.sleep(3)
    report = dict(status=result['status'], id=job_id, model_id=model_id,
                  revision=MODELS[model_id]['revision'], metadata=result)
    if result['status'] == 'completed':
        response = requests.get(f'http://127.0.0.1:8000/image/{job_id}?kind=generations', timeout=30)
        response.raise_for_status()
        image = Image.open(io.BytesIO(response.content)).convert('RGB')
        assert list(image.size) == result['output_size']
        assert max(ImageStat.Stat(image).stddev) > 5, 'Image appears blank'
        assert result['model_id'] == model_id
        (folder/(model_id+'-'+framing+'.png')).write_bytes(response.content)
        report['sha256'] = hashlib.sha256(response.content).hexdigest()
        report['output_size'] = list(image.size)
    (folder/(model_id+'-validation.json')).write_text(json.dumps(report, indent=2))
    if report['status'] != 'completed':
        raise SystemExit('Inference failed: '+result['message'])
    print('VERIFIED', model_id, report['output_size'], result['seconds'], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model_id')
    parser.add_argument('--framing', default='square')
    parser.add_argument('--steps', type=int, default=20)
    args = parser.parse_args()
    validate(args.model_id, args.framing, args.steps)
