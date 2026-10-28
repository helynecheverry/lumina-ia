"""Real browser upload → selected local pipeline → GridFS download → reload."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import requests
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.model_registry import MODELS


def run(model_id, steps):
    folder = ROOT/'artifacts/multi-model'
    folder.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
        page = browser.new_page(viewport={'width':1440,'height':1000})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto('http://127.0.0.1:8501/studio')
        page.wait_for_function("document.querySelector('#model-select').options.length===4")
        page.locator('#model-select').select_option(model_id)
        page.locator('#framing').select_option('portrait')
        page.locator('[data-personality="natural"]').click()
        page.locator('#demo-input').click()
        page.locator('#reference-preview').wait_for(state='visible')
        page.get_by_role('button',name='Perfil profesional',exact=True).click()
        page.locator('#custom-prompt').fill('Traje negro elegante, fondo gris, luz suave de estudio')
        page.locator('summary').filter(has_text='Ajustes de creación').click()
        if not page.locator('#steps').is_disabled():page.locator('#steps').select_option(str(steps))
        page.locator('#random-seed').uncheck()
        page.locator('#seed').fill('42817')
        page.locator('#generate').click()
        page.wait_for_url('**/studio?creation=*',timeout=45000)
        job_id = parse_qs(urlsplit(page.url).query)['creation'][0]
        print('SUBMITTED',model_id,job_id,flush=True)
        page.wait_for_function("!document.querySelector('#download-result').hidden || ['No completado','Cancelado','Interrumpido'].includes(document.querySelector('#job-status').textContent)",timeout=1200000)
        terminal=requests.get('http://127.0.0.1:8000/influencer/generations/'+job_id,timeout=20).json()
        assert terminal['status']=='completed',terminal
        with page.expect_download() as event:
            page.locator('#download-result').click()
        image_path = folder/(model_id+'-portrait.png')
        event.value.save_as(str(image_path))
        response=requests.get('http://127.0.0.1:8000/influencer/generations/'+job_id,timeout=20)
        response.raise_for_status()
        job=response.json()
        assert job['status']=='completed',job
        assert job['model_id']==model_id and job['framing']=='portrait',job
        config=requests.get('http://127.0.0.1:8000/influencer/config',timeout=15).json()
        assert list(Image.open(image_path).size)==config['models'][model_id]['resolutions']['portrait']
        assert 'black' in job['translated_prompt'].lower(),job
        assert 'vertical upper body' in job['effective_prompt'],job
        page.reload()
        page.locator('#download-result').wait_for(state='visible',timeout=45000)
        assert page.locator('#model-select').input_value()==model_id
        assert page.locator('#framing').input_value()=='portrait'
        assert page.locator('#steps').input_value()==str(job['steps'])
        page.screenshot(path=str(folder/(model_id+'-completed.png')),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        page.screenshot(path=str(folder/(model_id+'-mobile.png')),full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth')<=390
        assert not errors,errors
        report=dict(status='completed',model_id=model_id,revision=MODELS[model_id]['revision'],
                    id=job_id,metadata=job,output_size=job['output_size'],browser_errors=errors,
                    sha256=hashlib.sha256(image_path.read_bytes()).hexdigest(),
                    checks=['browser submit','selected pipeline','Spanish instruction','download','reload','mobile width'])
        (folder/(model_id+'-browser-validation.json')).write_text(json.dumps(report,indent=2))
        browser.close()
        print('VERIFIED',model_id,job['output_size'],job['seconds'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model_id',choices=MODELS)
    parser.add_argument('--steps',type=int,default=20)
    args=parser.parse_args()
    run(args.model_id,args.steps)
