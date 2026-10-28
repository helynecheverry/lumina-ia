"""Assemble the measured V2 results without claiming commercial-model parity."""
import datetime
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import requests

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/redesign'
results=json.loads((OUT/'generation_report.json').read_text())
assert len(results)==6 and all(j['status']=='completed' for j in results)
red,blue=[np.array(Image.open(OUT/(name+'.png')).convert('RGB')).astype(float) for name in ('red','blue')]
assert not np.array_equal(red,blue)
image_difference=float(np.abs(red-blue).mean())
font=ImageFont.truetype(str(ROOT/'web/assets/fonts/RobotoCondensed.ttf'),25)
comparison=Image.new('RGB',(1024,565),'#111315')
for i,(name,label) in enumerate([('red','Misma foto + semilla: chaqueta ROJA'),('blue','Misma foto + semilla: chaqueta AZUL')]):
 comparison.paste(Image.open(OUT/(name+'.png')),(i*512,0));ImageDraw.Draw(comparison).text((i*512+14,526),label,font=font,fill='white')
comparison.save(OUT/'prompt_ab.jpg',quality=93)
url=(OUT/'native_job_url.txt').read_text();job_id=parse_qs(urlsplit(url).query)['creation'][0]
job=requests.get('http://127.0.0.1:8000/influencer/generations/'+job_id,timeout=10).json()
assert job['status']=='completed' and 'green' in job['translated_prompt'].lower()
assert Image.open(OUT/'native_camera_result.png').size==(512,512)
log=(ROOT/'.runtime/logs/final_v2_tests.log').read_text()
assert 'Ran 15 tests' in log and '\nOK\n' in log,log
assert 'PASS native webcam' in (ROOT/'.runtime/logs/native_generation_test.log').read_text()
report={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'health':requests.get('http://127.0.0.1:8501/api/health',timeout=10).json(),
 'recipe_version':'2.0','catalog_size':32,'visually_checked_gpu_cases':6,
 'automated_tests':{'unit_and_browser_tests':15,'passed':True},
 'prompt_ab':{'same_seed':results[0]['seed']==results[1]['seed'],'seed':results[0]['seed'],
   'same_reference':True,'mean_absolute_pixel_difference_0_255':image_difference,
   'manual_observation':'Red clothing in A, blue/light blue clothing in B. This proves an observable change, not universal prompt accuracy.'},
 'actual_generations':results,'native_camera_end_to_end':{'passed':True,'simulated_camera':True,'job':job},
 'native_hd_download': (OUT/'native_hd.png').is_file() and Image.open(OUT/'native_hd.png').size==(1024,1024),
 'frontend':{'native_html_css_js':True,'port':8501,'header_px':36,'sidebar_px':320,
   'reference_layout':True,'pixel_identical_claim':False,'mobile_checked':True,
   'edits_and_restoration_preserved':True},
 'limits':['32 recipes validated structurally; 6 GPU cases visually checked, not all 32.',
   'Creative styles may substantially change face, presentation and identity likeness.',
   'Native generation remains 512x512. No claim of parity with Higgsfield private models.']}
(OUT/'validation_report.json').write_text(json.dumps(report,indent=2))
print('Report written:',OUT/'validation_report.json')
print('A/B mean pixel difference:',round(image_difference,2))
