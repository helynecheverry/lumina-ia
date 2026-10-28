"""Browser checks with a synthetic webcam; does not claim physical camera testing."""
from pathlib import Path
import sys
import json
import re
import cv2
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts' / 'local-influencer'
frame = cv2.cvtColor(cv2.imread(str(OUT / 'reference.png')), cv2.COLOR_BGR2YUV_I420).tobytes()
video = OUT / 'camera.y4m'
with video.open('wb') as file:
    file.write(b'YUV4MPEG2 W512 H512 F10:1 Ip A1:1 C420jpeg\n')
    for _ in range(20):
        file.write(b'FRAME\n' + frame)
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True,
        args=['--no-sandbox', '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream',
              '--use-file-for-fake-video-capture=' + str(video)])
    context = browser.new_context(viewport={'width': 1500, 'height': 1100}, permissions=['camera'])
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.goto('http://127.0.0.1:8501')
    page.get_by_text('Tú, en otra historia.', exact=True).wait_for(timeout=30000)
    page.get_by_text('Tu dirección creativa', exact=False).wait_for()
    page.screenshot(path=str(OUT / 'studio.png'), full_page=True)
    page.locator('input[type=file]').set_input_files(str(OUT / 'reference.png'))
    page.get_by_text('Tu foto de referencia', exact=True).wait_for()
    page.screenshot(path=str(OUT / 'upload.png'), full_page=True)
    assert page.get_by_role('button', name='✦ Crear mi retrato', exact=True).is_enabled()
    page.get_by_text('Usar cámara', exact=True).click()
    # Streamlit may show an explicit enable button before the video preview.
    print('Camera buttons:', page.get_by_role('button').all_text_contents(), flush=True)
    enable = page.get_by_role('button', name='Enable camera', exact=True)
    if enable.count():
        enable.click()
    capture = page.get_by_role('button', name='Take Photo', exact=False)
    capture.wait_for(timeout=20000)
    page.locator('video').wait_for()
    page.wait_for_function("document.querySelector('video')?.videoWidth > 0")
    capture.click()
    page.screenshot(path=str(OUT / 'camera_after_click.png'), full_page=True)
    page.get_by_text('Tu foto de referencia', exact=True).wait_for(timeout=15000)
    page.screenshot(path=str(OUT / 'camera.png'), full_page=True)
    assert page.get_by_role('button', name='✦ Crear mi retrato', exact=True).is_enabled()
    print('PASS: upload preview + simulated webcam capture + generate enabled', flush=True)
    if '--generate' in sys.argv:
        page.get_by_role('button', name='〰 Ilustración de autor', exact=True).click()
        page.get_by_text('Convierte tu referencia en una ilustración editorial.', exact=True).first.wait_for()
        page.get_by_role('button', name='✦ Crear mi retrato', exact=True).click()
        page.wait_for_url(re.compile(r'.*creation=.*'), timeout=30000)
        print('UI submitted:', page.url, flush=True)
        (OUT / 'browser_job_url.txt').write_text(page.url)
        page.get_by_text('Tu retrato generado con IA', exact=True).wait_for(timeout=300000)
        with page.expect_download() as download_info:
            page.get_by_role('button', name='↓ Descargar retrato', exact=True).click()
        download_info.value.save_as(str(OUT / 'camera_generated.png'))
        assert Image.open(OUT / 'camera_generated.png').size == (512,512)
        page.screenshot(path=str(OUT / 'camera_result.png'), full_page=True)
        print('PASS: webcam → UI submit → real model → displayed result → browser download', flush=True)
    assert not errors, errors
    browser.close()
