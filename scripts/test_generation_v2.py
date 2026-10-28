"""Real CUDA checks: fixed-seed Spanish prompt A/B and creative model styles."""
import json
import time
import uuid
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageFont

OUT=Path('artifacts/redesign'); OUT.mkdir(exist_ok=True)
raw=Path('artifacts/local-influencer/reference.png').read_bytes()
api='http://127.0.0.1:8000'
cases=[
 ('red','editorial','Llevo una chaqueta roja, fondo blanco',.55),
 ('blue','editorial','Llevo una chaqueta azul, fondo blanco',.55),
 ('pirate','pirate','Sombrero pirata con una pluma roja',.48),
 ('comic','comic','Traje de superhéroe rojo y azul',.4),
 ('anime','anime','Chaqueta amarilla, flores de cerezo en el fondo',.35),
 ('clay','clay','Muñeco de plastilina verde con gafas redondas',.34),
]
results=[]
for name,preset,prompt,influence in cases:
 response=requests.post(api+'/influencer/generations',files={'file':('test-v2.png',raw,'image/png')},
     data={'preset':preset,'prompt':prompt,'identity_strength':influence,'steps':28,'seed':18423,'request_key':str(uuid.uuid4())},timeout=30)
 response.raise_for_status(); job=response.json(); print('START',name,job['id'],flush=True)
 last=None
 for _ in range(240):
  response=requests.get(api+'/influencer/generations/'+job['id'],timeout=20); response.raise_for_status();job=response.json()
  if job['progress']!=last: print(name,job['status'],job['progress'],flush=True);last=job['progress']
  if job['status'] not in ('queued','processing'):break
  time.sleep(3)
 assert job['status']=='completed',job
 image=requests.get(api+'/image/'+job['id'],params={'kind':'generations'},timeout=30);image.raise_for_status()
 (OUT/(name+'.png')).write_bytes(image.content)
 (OUT/(name+'.json')).write_text(json.dumps(job,indent=2))
 assert job['recipe_version'].startswith('2.')
 assert job['prompt_language']=='es',job
 if name in ('red','blue'):
  assert name in job['translated_prompt'].lower(),job
  assert 'designer jacket' not in job['effective_prompt'],job
 if preset in ('pirate','comic','anime','clay'):
  Path('app/assets/portraits/'+preset+'.png').write_bytes(image.content)
 results.append(job)
 print('PASS',name,job['seconds'],job['translated_prompt'],flush=True)
(OUT/'generation_report.json').write_text(json.dumps(results,indent=2))
board=Image.new('RGB',(1536,1120),'#131517');font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',20)
for i,(name,*_) in enumerate(cases):
 x,y=(i%3)*512,(i//3)*560
 board.paste(Image.open(OUT/(name+'.png')),(x,y))
 ImageDraw.Draw(board).text((x+12,y+525),name,font=font,fill='white')
board.save(OUT/'generation_comparison.jpg',quality=92)
print('ALL V2 GENERATIONS PASS',flush=True)
