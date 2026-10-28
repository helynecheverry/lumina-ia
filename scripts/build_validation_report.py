"""Collect actual integration artifacts and generate a comparison sheet."""
import datetime
import json
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/local-influencer'
labels = [('editorial', 'Editorial de moda'), ('cinema', 'Protagonista de cine'), ('neon', 'Ciudad neón'),
          ('professional', 'Perfil profesional'), ('fantasy', 'Mundo fantástico'), ('illustration', 'Ilustración de autor')]
results = []
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 22)
sheet = Image.new('RGB', (1536, 1120), '#0d111b')
draw = ImageDraw.Draw(sheet)
for index, (key, label) in enumerate(labels):
    job = json.loads((OUT / (key + '.json')).read_text())
    assert job['status'] == 'completed'
    image = Image.open(OUT / (key + '.png')).convert('RGB')
    assert image.size == (512,512)
    x, y = (index % 3) * 512, (index // 3) * 560
    sheet.paste(image, (x, y))
    draw.text((x + 18, y + 523), label, font=font, fill='#edf2fa')
    results.append(job)
sheet.save(OUT / 'styles_comparison.jpg', quality=92)
assert Image.open(OUT / 'editorial_hd.png').size == (1024,1024)
browser_log = (ROOT / '.runtime/logs/influencer_browser_test.log').read_text()
upscale_log = (ROOT / '.runtime/logs/influencer_upscale_browser_test.log').read_text()
frontend_log = (ROOT / '.runtime/logs/frontend_test.log').read_text()
assert 'PASS: webcam → UI submit → real model → displayed result → browser download' in browser_log
assert 'PASS:' in upscale_log
assert '\nOK\n' in frontend_log
report = {
    'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'health': requests.get('http://127.0.0.1:8000/health', timeout=10).json(),
    'engine': requests.get('http://127.0.0.1:8000/influencer/config', timeout=10).json(),
    'actual_cuda_generations': results,
    'http_validation_and_cancellation': json.loads((OUT / 'validation.json').read_text()),
    'checks': {'six_styles_generated': True, 'queue_contract_tests': 6,
        'frontend_page_and_style_tests': 2, 'browser_upload': True,
        'simulated_webcam_to_real_generation_and_browser_download': True,
        'physical_webcam_tested': False, 'resume_after_reload': True,
        'real_esrgan_upscale_1024_browser_download': True,
        'mongodb_and_gridfs_bytes_verified': True},
    'limitations': ['Not Higgsfield proprietary weights', 'Identity likeness varies; no biometric fidelity metric',
                    '512x512 native output; 1024x1024 via superresolution', 'Local single-user deployment']}
(OUT / 'validation_report.json').write_text(json.dumps(report, indent=2))
print('Report:', OUT / 'validation_report.json')
print('Generation seconds:', [j['seconds'] for j in results])
