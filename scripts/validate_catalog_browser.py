"""Check all published illustrations and their actual browser rendering."""
import hashlib
import io
import json
from pathlib import Path
import requests
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/catalog-complete'

def main():
    config=requests.get('http://127.0.0.1:8000/influencer/config',timeout=20).json()
    records=[]
    for kind,items,prefix in [('style',config['presets'],'examples'),('character',config['character_types'],'characters')]:
        for key,item in items.items():
            assert item['preview_available'],(kind,key)
            response=requests.get(f'http://127.0.0.1:8501/{prefix}/{key}.png',timeout=20)
            response.raise_for_status()
            img=Image.open(io.BytesIO(response.content));img.verify()
            records.append(dict(kind=kind,key=key,sha256=hashlib.sha256(response.content).hexdigest()))
    assert len(records)==44
    for kind in ['style','character']:
        hashes=[r['sha256'] for r in records if r['kind']==kind]
        assert len(hashes)==len(set(hashes)),kind
    errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1440,'height':1000})
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto('http://127.0.0.1:8501/studio')
        page.wait_for_function("document.querySelectorAll('#style-options button').length===32")
        assert page.locator('[data-personality]').count()==12
        for card in page.locator('#style-options button').all():
            card.scroll_into_view_if_needed()
            image=card.locator('img')
            assert image.count()==1
            image.evaluate('(img)=>img.decode()')
            assert image.evaluate('(img)=>img.naturalWidth>0')
        page.locator('#style-options button').first.scroll_into_view_if_needed()
        page.screenshot(path=str(OUT/'catalog-desktop.png'))
        page.set_viewport_size({'width':390,'height':844})
        page.get_by_role('button',name='Abrir configuración').click()
        assert page.evaluate('document.documentElement.scrollWidth')<=390
        page.screenshot(path=str(OUT/'catalog-mobile.png'))
        browser.close()
    assert not errors,errors
    report=dict(status='completed',styles=32,characters=12,images=records,browser_errors=errors)
    (OUT/'catalog-validation.json').write_text(json.dumps(report,indent=2))
    print('PASS: 32 style images, 12 character images, unique PNGs, desktop/mobile rendering')

if __name__=='__main__':main()
