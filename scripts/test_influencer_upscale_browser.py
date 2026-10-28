"""Resume an existing portrait, upscale via the UI, verify its browser download."""
import json
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/local-influencer'
job = json.loads((OUT / 'editorial.json').read_text())
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True, args=['--no-sandbox'])
    page = browser.new_page(viewport={'width':1500,'height':1150})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://127.0.0.1:8501/?creation=' + job['id'])
    page.get_by_text('Tu retrato generado con IA', exact=True).wait_for(timeout=30000)
    page.get_by_role('button', name='✦ Mejorar detalle ×2 con Real-ESRGAN', exact=True).click()
    hd = page.get_by_role('button', name='↓ Descargar versión 1024 × 1024', exact=True)
    hd.wait_for(timeout=300000)
    with page.expect_download() as download_info:
        hd.click()
    download_info.value.save_as(str(OUT / 'editorial_hd.png'))
    assert Image.open(OUT / 'editorial_hd.png').size == (1024,1024)
    page.screenshot(path=str(OUT / 'completed_studio.png'), full_page=True)
    page.get_by_text('Mi galería', exact=True).click()
    page.get_by_text('Tu galería de resultados', exact=True).wait_for()
    page.get_by_role('button', name='Descargar', exact=True).first.wait_for()
    page.screenshot(path=str(OUT / 'gallery.png'), full_page=True)
    assert not errors, errors
    browser.close()
print('PASS: restored job after reload + Real-ESRGAN ×2 + 1024 PNG download + gallery')
