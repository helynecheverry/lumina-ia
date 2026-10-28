"""Real image regression: UI-selected Atrevido, then matched natural/extreme cases."""
import json
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit,parse_qs

import requests
from PIL import Image,ImageDraw,ImageFont
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/character-types';OUT.mkdir(parents=True,exist_ok=True)
API='http://127.0.0.1:8000'
raw=(ROOT/'web/assets/demo-reference.jpg').read_bytes()
SEED=18423
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':1440,'height':1000})
 errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
 page.goto('http://127.0.0.1:8501')
 page.locator('#connection.connected').wait_for()
 page.get_by_role('button',name='Atrevido',exact=True).click()
 page.get_by_role('link',name='Genera tu influencer',exact=True).click()
 page.locator('[data-personality="bold"][aria-pressed="true"]').wait_for()
 page.get_by_role('button',name='Probar ejemplo',exact=True).click()
 page.locator('#reference-preview').wait_for(state='visible')
 page.get_by_role('button',name='Editorial de moda',exact=True).click()
 page.locator('summary').filter(has_text='Ajustes de creación').click()
 page.locator('#steps').select_option('20')
 slider=page.locator('#identity');slider.focus();slider.press('Home')
 for _ in range(5):slider.press('ArrowRight')
 page.locator('#random-seed').uncheck();page.locator('#seed').fill(str(SEED))
 page.get_by_role('button',name='Generar',exact=True).click()
 page.wait_for_url('**/studio?creation=*',timeout=30000)
 job_id=parse_qs(urlsplit(page.url).query)['creation'][0]
 print('UI bold submitted:',job_id,flush=True)
 job=requests.get(API+'/influencer/generations/'+job_id,timeout=10).json()
 assert job['character_type']=='bold',job
 assert job['seed']==SEED and job['steps']==20 and job['identity_strength']==.55,job
 page.locator('#download-result').wait_for(state='visible',timeout=300000)
 with page.expect_download() as downloaded:
  page.get_by_role('link',name='Descargar imagen ↓',exact=True).click()
 downloaded.value.save_as(str(OUT/'bold.png'))
 job=requests.get(API+'/influencer/generations/'+job_id,timeout=10).json()
 assert job['status']=='completed' and 'avant-garde' in job['effective_prompt'],job
 assert job['character_label']=='Atrevido'
 (OUT/'bold.json').write_text(json.dumps(job,indent=2))
 page.reload()
 page.locator('#download-result').wait_for(state='visible',timeout=30000)
 page.locator('[data-personality="bold"][aria-pressed="true"]').wait_for()
 assert 'Atrevido' in page.locator('#result-metadata').inner_text()
 page.screenshot(path=str(OUT/'bold-ui.png'))
 assert not errors,errors
 browser.close()
print('PASS UI bold generation + persistence + reload',flush=True)
for kind in ('natural','extreme'):
 response=requests.post(API+'/influencer/generations',files={'file':('reference.jpg',raw,'image/jpeg')},
   data={'character_type':kind,'preset':'editorial','prompt':'','steps':20,'seed':SEED,
         'identity_strength':.55,'request_key':str(uuid.uuid4())},timeout=20)
 response.raise_for_status();job=response.json();last=None
 for _ in range(150):
  response=requests.get(API+'/influencer/generations/'+job['id'],timeout=15);response.raise_for_status();job=response.json()
  if job['progress']!=last:print(kind,job['progress'],job['message'],flush=True);last=job['progress']
  if job['status'] not in ('queued','processing'):break
  time.sleep(3)
 assert job['status']=='completed' and job['character_type']==kind,job
 image=requests.get(API+'/image/'+job['id'],params={'kind':'generations'},timeout=20);image.raise_for_status()
 (OUT/(kind+'.png')).write_bytes(image.content);(OUT/(kind+'.json')).write_text(json.dumps(job,indent=2))
 print('PASS',kind,job['seconds'],flush=True)
font=ImageFont.truetype(str(ROOT/'web/assets/fonts/RobotoCondensed.ttf'),25)
board=Image.new('RGB',(1536,565),'#111315')
for index,(kind,label) in enumerate([('natural','Natural'),('bold','Atrevido'),('extreme','Extremo')]):
 board.paste(Image.open(OUT/(kind+'.png')).convert('RGB'),(index*512,0))
 ImageDraw.Draw(board).text((index*512+15,525),label+' · misma foto y semilla',font=font,fill='white')
board.save(OUT/'comparison.jpg',quality=94)
(OUT/'report.json').write_text(json.dumps({'same_seed':SEED,'same_input':True,'same_style':'editorial',
 'same_identity_strength':.55,'actual_generations':{kind:json.loads((OUT/(kind+'.json')).read_text()) for kind in ('natural','bold','extreme')},
 'ui_bold_generation_and_reload_passed':True},indent=2))
print('ALL CHARACTER TYPE CHECKS PASS',flush=True)
