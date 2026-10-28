"""Apply the known BasicSR 1.4.2 import compatibility fix for torchvision >=0.17."""
from importlib.util import find_spec
from pathlib import Path
spec = find_spec('basicsr')
if spec is None:
    raise SystemExit('Instale requirements.lock.txt primero')
path = Path(spec.origin).parent / 'data' / 'degradations.py'
text = path.read_text()
old = 'from torchvision.transforms.functional_tensor import rgb_to_grayscale'
new = 'from torchvision.transforms.functional import rgb_to_grayscale'
if old in text:
    path.write_text(text.replace(old, new))
    print('BasicSR actualizado para torchvision moderno')
else:
    print('BasicSR ya es compatible')
from realesrgan import RealESRGANer
print('Importación Real-ESRGAN OK')
