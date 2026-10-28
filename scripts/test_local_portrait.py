import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.influencer_engine import generate
from skimage import data
from PIL import Image
import io,json
out=Path('artifacts/local-influencer');out.mkdir(parents=True,exist_ok=True)
buffer=io.BytesIO(); Image.fromarray(data.astronaut()).save(buffer,'PNG')
raw=buffer.getvalue();(out/'reference.png').write_bytes(raw)
image,meta=generate(raw, preset='cinema', seed=9241, steps=20, progress=lambda p,m:print(p,m,flush=True))
(out/'cinema.png').write_bytes(image)
(out/'cinema.json').write_text(json.dumps(meta,indent=2))
print(meta,flush=True)
