"""Run resumable sequential API experiments with private images and a local report."""
import argparse
import hashlib
import html
import io
import json
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    temp.replace(path)


def report(out, cases):
    cards = []
    for path in sorted(out.glob('*/record.json')):
        record = json.loads(path.read_text())
        case = record['case']
        job = record.get('job', {})
        image = f'<img src="{case["id"]}/result.png" alt="Resultado {case["id"]}">' if record.get('status') == 'completed' else ''
        review = record.get('review', {'status': 'pending', 'note': 'Revisión visual pendiente; no equivale a mejora aprobada.'})
        cards.append(f'<article><h2>{html.escape(case["id"])}</h2>{image}<p>{html.escape(str(record["status"]))} · {html.escape(str(job.get("seconds", "?")))} s</p><pre>{html.escape(json.dumps(case, indent=2, ensure_ascii=False))}</pre><p>{html.escape(json.dumps(review, ensure_ascii=False))}</p><a href="{case["id"]}/record.json">Registro completo</a></article>')
    (out/'index.html').write_text('<!doctype html><html lang="es"><meta charset="utf-8"><title>Pruebas de calidad Lúmina</title><style>body{font-family:system-ui;background:#17191d;color:#eee;margin:24px}main{display:flex;flex-wrap:wrap;gap:20px}article{width:320px;background:#252931;padding:16px}img{width:100%;height:320px;object-fit:contain}pre{white-space:pre-wrap}a{color:#c7f36b}</style><h1>Pruebas de calidad Lúmina</h1><p>Privado. Referencia y resultados reales. La aceptación de parecido requiere revisión del propietario.</p><p><a href="session.json">Entorno y versiones</a> · <a href="weights-evidence.json">Pesos y hashes</a></p><main><article><h2>Referencia</h2><img src="reference.png" alt="Referencia usada"></article>'+''.join(cards)+'</main></html>')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--cases', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--api', default='http://127.0.0.1:8000')
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text())
    identifiers = [case['id'] for case in cases]
    if len(set(identifiers)) != len(identifiers) or any(not x or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in x) for x in identifiers):
        raise ValueError('Cada caso requiere un id único formado por letras minúsculas, números, guion o guion bajo.')
    args.out.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    Image.open(args.reference).convert('RGB').save(buffer, format='PNG')
    raw = buffer.getvalue()
    ref_hash = digest(raw)
    old_reference = args.out/'reference.png'
    if old_reference.exists() and old_reference.read_bytes() != raw:
        raise ValueError('No mezcles referencias distintas en una misma sesión.')
    old_reference.write_bytes(raw)
    session_path = args.out/'session.json'
    if not session_path.exists():
        sources = sorted((ROOT/'app').glob('*.py')) + [Path(__file__)]
        save(session_path, {'created_utc': datetime.now(timezone.utc).isoformat(), 'reference_sha256': ref_hash,
            'git_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'git_status': subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True),
            'source_sha256': {p.relative_to(ROOT).as_posix(): digest(p.read_bytes()) for p in sources},
            'models': requests.get(args.api+'/influencer/models',timeout=30).json()})
    client = requests.Session()
    for case in cases:
        folder = args.out/case['id']; folder.mkdir(exist_ok=True)
        path = folder/'record.json'
        record = json.loads(path.read_text()) if path.exists() else {'case': case, 'reference_sha256':ref_hash, 'status':'prepared', 'created_utc':datetime.now(timezone.utc).isoformat()}
        if record['case'] != case:
            raise ValueError('No cambies un caso existente: crea otro identificador.')
        if record['status'] in ('completed','failed'):
            continue
        if 'provenance' not in record:
            record['provenance'] = {
                'source_sha256': {p.relative_to(ROOT).as_posix(): digest(p.read_bytes()) for p in sorted((ROOT/'app').glob('*.py'))},
                'runner_sha256': digest(Path(__file__).read_bytes()),
                'git_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                'git_diff_sha256': digest(subprocess.check_output(['git','diff','HEAD'],cwd=ROOT)),
            }
            (folder/'source.patch').write_bytes(subprocess.check_output(['git','diff','HEAD'],cwd=ROOT))
        save(path, record)
        try:
            if 'job_id' not in record:
                data = {k:v for k,v in case.items() if k != 'id'}
                data['appearance'] = json.dumps(data.get('appearance',{}))
                data['request_key'] = str(uuid.uuid5(uuid.NAMESPACE_URL, str(args.out.resolve())+case['id']+ref_hash))
                response=client.post(args.api+'/influencer/generations',files={'file':('experiment.png',raw,'image/png')},data=data,timeout=60)
                response.raise_for_status();job=response.json()
                record.update(job_id=job['id'],status='submitted',job=job);save(path,record)
            print('START',case['id'],record['job_id'],flush=True)
            deadline=time.monotonic()+1800
            while time.monotonic()<deadline:
                response=client.get(args.api+'/influencer/generations/'+record['job_id'],timeout=60);response.raise_for_status();job=response.json()
                record['job']=job;save(path,record)
                if job['status'] not in ('queued','processing'):
                    break
                time.sleep(3)
            else:
                raise TimeoutError('Trabajo aún activo; se puede reanudar esta sesión sin duplicarlo.')
            if job['status'] != 'completed':
                record.update(status='failed',error=job.get('message',job['status']))
            else:
                response=client.get(args.api+'/influencer/generations/'+job['id']+'/reference',timeout=60);response.raise_for_status();stored=response.content
                (folder/'stored-reference.png').write_bytes(stored)
                record['stored_reference_sha256']=digest(stored)
                record['reference_pixels_match']=Image.open(io.BytesIO(stored)).convert('RGB').size == Image.open(io.BytesIO(raw)).size and Image.open(io.BytesIO(stored)).convert('RGB').tobytes()==Image.open(io.BytesIO(raw)).convert('RGB').tobytes()
                if not record['reference_pixels_match']:
                    raise ValueError('La referencia guardada no coincide con la enviada.')
                response=client.get(args.api+'/image/'+job['id'],params={'kind':'generations'},timeout=60);response.raise_for_status()
                result=response.content;decoded=Image.open(io.BytesIO(result));decoded.load()
                (folder/'result.png').write_bytes(result)
                record.pop('error', None)
                record.pop('error_response', None)
                record.update(status='completed',result_sha256=digest(result),output_size=list(decoded.size),review={'status':'pending'})
            record['finished_utc'] = datetime.now(timezone.utc).isoformat()
            record['elapsed_including_queue_s'] = round((datetime.fromisoformat(record['finished_utc']) - datetime.fromisoformat(record['created_utc'])).total_seconds(), 3)
            save(path,record);report(args.out,cases)
            print('DONE',case['id'],record['status'],job.get('seconds'),flush=True)
        except Exception as exc:
            record['error']=str(exc)
            if isinstance(exc, requests.HTTPError) and exc.response is not None:
                record['error_response'] = exc.response.text
            record.setdefault('errors', []).append({'at': datetime.now(timezone.utc).isoformat(), 'message': record['error']})
            record['finished_utc'] = datetime.now(timezone.utc).isoformat()
            record['elapsed_including_queue_s'] = round((datetime.fromisoformat(record['finished_utc']) - datetime.fromisoformat(record['created_utc'])).total_seconds(), 3)
            save(path,record);report(args.out,cases)
            print('ERROR',case['id'],str(exc),flush=True)
            # Preserve submitted jobs for resume; do not submit more while their state is uncertain.
            raise
    report(args.out,cases)


if __name__ == '__main__':
    main()
