"""Fetch public character reference art with source hashes; no user photo upload."""
import sys,json,hashlib,io,time
from pathlib import Path
import requests
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.discovery_catalog import ENTRIES,ASSETS

def main():
 session=requests.Session()
 r=session.get('https://digimon-api.vercel.app/api/digimon',timeout=30);r.raise_for_status()
 digimon={x['name'].lower():x['img'] for x in r.json()}
 manifest=[]
 for item in ENTRIES.values():
  if item['category']=='zodiac':continue
  target=ASSETS/item['category']/(item['key']+'.png');target.parent.mkdir(parents=True,exist_ok=True)
  url=(f'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{item["artwork_id"]}.png' if item['category']=='pokemon' else digimon.get(item['name'].lower()))
  if not url:raise RuntimeError('Sin fuente para '+item['name'])
  if not target.exists():
   response=session.get(url,timeout=30);response.raise_for_status();im=Image.open(io.BytesIO(response.content));im.load();im.convert('RGBA').save(target)
  manifest.append(dict(id=item['id'],path=target.relative_to(ROOT).as_posix(),source=url,sha256=hashlib.sha256(target.read_bytes()).hexdigest(),usage='Character reference artwork for a local fan experience; character rights belong to their respective owners. Not locally generated artwork.'))
  print('READY',item['id'],flush=True)
 ASSETS.mkdir(parents=True,exist_ok=True);(ASSETS/'sources.json').write_text(json.dumps({'catalog_version':'1.0','sources':manifest},indent=2)+'\n')
if __name__=='__main__':main()
