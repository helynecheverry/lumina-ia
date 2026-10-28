"""Real visual controls through UI, inference, download and history restore."""
import json
from pathlib import Path
from urllib.parse import parse_qs,urlsplit

import requests
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/catalog-complete'


def main():
    chosen={'presentation':'masculine','outfit':'red_jacket','scene':'blue_studio','lighting':'dramatic'}
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1440,'height':1000})
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto('http://127.0.0.1:8501/studio')
        page.wait_for_function("document.querySelector('#character-options').children.length>=10")
        page.locator('#model-select').select_option('flux_klein')
        page.locator('[data-personality="natural"]').click()
        page.get_by_role('button',name='Editorial de moda',exact=True).click()
        for key,value in chosen.items():
            page.locator('#'+key+'-choices').locator('..').locator('summary').click()
            button=page.locator('[data-appearance-group="'+key+'"][data-appearance-value="'+value+'"]')
            button.click()
            assert button.get_attribute('aria-pressed')=='true'
        page.locator('#preview-prompt').click()
        page.locator('#prompt-preview').wait_for(state='visible',timeout=45000)
        assert 'red jacket' in page.locator('#prompt-preview').inner_text()
        assert 'plain blue studio background' in page.locator('#prompt-preview').inner_text()
        page.locator('#demo-input').click()
        page.locator('#reference-preview').wait_for(state='visible')
        page.locator('#generate').click()
        page.wait_for_url('**/studio?creation=*',timeout=45000)
        job_id=parse_qs(urlsplit(page.url).query)['creation'][0]
        print('SUBMITTED',job_id,flush=True)
        page.wait_for_function("!document.querySelector('#download-result').hidden || document.querySelector('#job-status').textContent==='No completado'",timeout=900000)
        result=requests.get('http://127.0.0.1:8000/influencer/generations/'+job_id,timeout=20).json()
        assert result['status']=='completed',result
        assert result['appearance']==chosen,result
        for word in ['masculine presentation','red jacket','plain blue studio background','dramatic cinematic lighting']:
            assert word in result['effective_prompt'],word
        assert 'warm neutral background' not in result['effective_prompt']
        with page.expect_download() as download:page.locator('#download-result').click()
        destination=OUT/'visual-controls-result.png'
        download.value.save_as(str(destination))
        assert list(Image.open(destination).size)==result['output_size']
        page.reload();page.locator('#download-result').wait_for(state='visible',timeout=45000)
        for key,value in chosen.items():
            assert page.locator('#'+key).input_value()==value
            button=page.locator('[data-appearance-group="'+key+'"][data-appearance-value="'+value+'"]')
            assert button.get_attribute('aria-pressed')=='true'
        page.screenshot(path=str(OUT/'controls-completed.png'),full_page=True)
        assert not errors,errors
        (OUT/'visual-controls-validation.json').write_text(json.dumps({'status':'completed','job':result,'browser_errors':errors,
            'checks':['all four panels','direct option buttons','prompt preview','real generation','Mongo persistence','download','history restore']},indent=2))
        browser.close()
        print('COMPLETE',result['output_size'],result['seconds'],flush=True)


if __name__=='__main__':main()
