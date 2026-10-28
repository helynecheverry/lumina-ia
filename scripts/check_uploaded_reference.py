"""Generate a neutral portrait from an explicit local reference, never a demo fallback."""
import hashlib,json,sys,time,uuid
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
source=Path(sys.argv[1]);out=ROOT/'artifacts/reference-diagnosis';out.mkdir(exist_ok=True)
raw=source.read_bytes()
model=sys.argv[2] if len(sys.argv)>2 else 'flux_klein'
character=sys.argv[3] if len(sys.argv)>3 else 'natural'
response=requests.post('http://127.0.0.1:8000/influencer/generations',files={'file':('reference-check.png',raw,'image/png')},data={'model_id':model,'preset':'professional','character_type':character,'prompt':'','appearance':'{}','seed':42817,'steps':4 if model=='flux_klein' else 20,'identity_strength':.75,'request_key':str(uuid.uuid4())},timeout=30)
response.raise_for_status();job=response.json();print('JOB',job['id'],flush=True)
for attempt in range(240):
    job=requests.get('http://127.0.0.1:8000/influencer/generations/'+job['id'],timeout=30).json()
    if job['status'] not in ('queued','processing'):break
    time.sleep(3)
assert job['status']=='completed',job
reference=requests.get('http://127.0.0.1:8000/influencer/generations/'+job['id']+'/reference',timeout=30).content
assert reference==raw,'Persisted reference differs from the uploaded normalized PNG'
result=requests.get('http://127.0.0.1:8000/image/'+job['id']+'?kind=generations',timeout=30);result.raise_for_status()
(out/('male-'+model+'-'+character+'-result.png')).write_bytes(result.content)
report=dict(status='completed',reference_sha256=hashlib.sha256(raw).hexdigest(),stored_reference_sha256=hashlib.sha256(reference).hexdigest(),job=job)
(out/('male-'+model+'-'+character+'-validation.json')).write_text(json.dumps(report,indent=2));print('COMPLETED',job['seconds'],flush=True)
