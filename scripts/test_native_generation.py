"""Real native UI camera → Spanish instruction → local generation → download."""
import json
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/redesign'
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox',
   '--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream',
   '--use-file-for-fake-video-capture='+str(ROOT/'artifacts/local-influencer/camera.y4m')])
 context=browser.new_context(viewport={'width':1440,'height':1000},permissions=['camera'])
 page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:8501/studio')
 page.get_by_role('button',name='Usar cámara',exact=False).click()
 page.wait_for_function("document.querySelector('#camera-video').videoWidth > 0")
 page.get_by_role('button',name='Tomar foto ◉',exact=True).click()
 page.locator('#reference-preview').wait_for(state='visible')
 page.get_by_role('button',name='Perfil profesional',exact=True).click()
 page.locator('#custom-prompt').fill('Llevo una chaqueta verde, fondo blanco')
 page.locator('summary').filter(has_text='Ajustes de creación').click()
 page.locator('#steps').select_option('20')
 page.get_by_role('button',name='Generar',exact=True).click()
 page.wait_for_url('**/studio?creation=*',timeout=30000)
 print('SUBMITTED',page.url,flush=True)
 (OUT/'native_job_url.txt').write_text(page.url)
 page.locator('#download-result').wait_for(state='visible',timeout=300000)
 with page.expect_download() as event:
  page.get_by_role('link',name='Descargar imagen ↓',exact=True).click()
 event.value.save_as(str(OUT/'native_camera_result.png'))
 assert Image.open(OUT/'native_camera_result.png').size==(512,512)
 page.locator('#used-prompt').evaluate('el=>el.open=true')
 assert 'green' in page.locator('#used-prompt-text').inner_text().lower()
 page.screenshot(path=str(OUT/'native_completed.png'))
 assert not errors,errors
 browser.close()
print('PASS native webcam + Spanish customization + real GPU image + browser download',flush=True)
