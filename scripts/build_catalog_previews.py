"""Resumable actual local generations for every style and character card."""
import sys
import argparse
import hashlib
import io
import json
import time
import uuid
from pathlib import Path

import requests
from PIL import Image, ImageStat

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/catalog-complete'
API='http://127.0.0.1:8000'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, default=ROOT/'web/assets/demo-reference.png',
                        help='Foto autorizada para crear ejemplos públicos; los PNG se versionan en Git.')
    parser.add_argument('--model', default='portrait_sd15')
    parser.add_argument('--refresh-characters', nargs='?', const='all',
                        help='Regenerar todos o una lista de personajes separada por comas.')
    args = parser.parse_args()
    raw = args.reference.read_bytes()
    reference_sha256 = hashlib.sha256(raw).hexdigest()
    reference_mime = Image.MIME.get(Image.open(io.BytesIO(raw)).format, 'application/octet-stream')
    OUT.mkdir(parents=True,exist_ok=True)
    config=requests.get(API+'/influencer/config',timeout=20).json()
    path=OUT/'preview-generations.json'
    records=json.loads(path.read_text()) if path.exists() else []
    cases=[]
    for group,items,target in [('style',config['presets'],ROOT/'app/assets/portraits'),
                               ('character',config['character_types'],ROOT/'app/assets/characters')]:
        target.mkdir(parents=True,exist_ok=True)
        for index,(key,item) in enumerate(items.items()):
            refresh = args.refresh_characters
            force = group == 'character' and refresh is not None and (refresh == 'all' or key in refresh.split(','))
            if (target/(key+'.png')).is_file() and not force:
                continue
            cases.append((group,key,index,item,target))
    cases.sort(key=lambda case:(case[0]!='character',case[2]))
    # Every output has its own real job and recorded recipe, never a renamed duplicate.
    for group,key,index,item,target in cases:
        model = args.model
        preset=key if group=='style' else ('three_d' if item.get('backbone')=='art' else 'editorial')
        character=key if group=='character' else 'natural'
        strength=(item['identity'] if group=='style' else min(.6+item['identity_offset'],item.get('max_identity',1.2)))
        strength=max(.3,min(1.2,strength))
        for attempt in range(2):
            response=requests.post(API+'/influencer/generations',files={'file':('preview-reference'+args.reference.suffix, raw, reference_mime)},
                data=dict(model_id=model,preset=preset,character_type=character,steps=4 if model=='flux_klein' else 20,
                          seed=18423+index+attempt*100,identity_strength=strength,request_key=str(uuid.uuid4())),timeout=30)
            response.raise_for_status()
            job=response.json();job_id=job['id'];print('START',group,key,job_id,flush=True)
            deadline=time.monotonic()+1200
            while time.monotonic()<deadline:
                response=requests.get(API+'/influencer/generations/'+job_id,timeout=60)
                response.raise_for_status();job=response.json()
                if job['status'] not in ('queued','processing'):break
                time.sleep(3)
            if job['status']=='completed':break
            print('RETRY',group,key,job.get('message'),flush=True)
        if job['status']!='completed':raise RuntimeError(f'{group}/{key}: {job}')
        image=requests.get(API+'/image/'+job_id,params={'kind':'generations'},timeout=30)
        image.raise_for_status()
        decoded=Image.open(io.BytesIO(image.content)).convert('RGB')
        assert decoded.size==(512,512)
        assert max(ImageStat.Stat(decoded).stddev)>5
        assert job['character_type']==character and job['preset']==preset
        (target/(key+'.png')).write_bytes(image.content)
        records.append(dict(reference_sha256=reference_sha256,group=group,key=key,job_id=job_id,sha256=hashlib.sha256(image.content).hexdigest(),
                            path=str((target/(key+'.png')).relative_to(ROOT)),metadata=job))
        path.write_text(json.dumps(records,indent=2))
        print('DONE',group,key,job['seconds'],flush=True)
    final=requests.get(API+'/influencer/config',timeout=20).json()
    assert all(item['preview_available'] for item in final['presets'].values())
    assert len(final['character_types'])>=10
    assert all(item['preview_available'] for item in final['character_types'].values())
    print('COMPLETE',len(final['presets']),'styles',len(final['character_types']),'characters',flush=True)


if __name__=='__main__':main()
