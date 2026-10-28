"""Small CPU-only CLIP affinity matcher. Scores are not identity probabilities."""
import gc
import hashlib
import json
import time
from pathlib import Path
import numpy as np
from PIL import Image
from app.discovery_catalog import ASSETS,ENTRIES,CATEGORIES,VERSION,public_catalog

ROOT=Path(__file__).resolve().parents[1]
MODEL=ROOT/'weights/discovery/clip'
REPO='openai/clip-vit-base-patch32'
REVISION='3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268'

def readiness():
 return (MODEL/'pytorch_model.bin').is_file() and (MODEL/'config.json').is_file()

def cache_key():
 payload=json.dumps(ENTRIES,sort_keys=True).encode()+REVISION.encode()
 for item in ENTRIES.values():
  p=ASSETS/item['category']/(item['key']+'.png')
  if p.is_file():payload+=hashlib.sha256(p.read_bytes()).digest()
 return hashlib.sha256(payload).hexdigest()[:20]

def reference_image(path):
 image=Image.open(path).convert('RGBA')
 background=Image.new('RGBA',image.size,(240,240,240,255));background.alpha_composite(image)
 return background.convert('RGB')

def normalize(values):
 return values/np.maximum(np.linalg.norm(values,axis=-1,keepdims=True),1e-8)

def rank(category,query,ids,image_vectors,text_vectors,limit=3):
 if category not in CATEGORIES:raise ValueError('Universo desconocido.')
 query=normalize(np.asarray(query,dtype=np.float32).reshape(1,-1))[0]
 results=[]
 for i,identifier in enumerate(ids):
  item=ENTRIES[str(identifier)]
  if item['category']!=category:continue
  text_score=float(query@text_vectors[i])
  score=text_score if category=='zodiac' else .75*float(query@image_vectors[i])+.25*text_score
  results.append((str(identifier),score))
 return sorted(results,key=lambda value:(-value[1],value[0]))[:limit]

class ClipSession:
 def __enter__(self):
  import torch
  from transformers import CLIPModel,CLIPProcessor
  if not readiness():raise ValueError('El reconocimiento visual no está instalado. Puedes elegir un personaje manualmente.')
  torch.set_num_threads(2)
  self.model=CLIPModel.from_pretrained(MODEL,local_files_only=True,low_cpu_mem_usage=True).eval().to('cpu')
  self.processor=CLIPProcessor.from_pretrained(MODEL,local_files_only=True,use_fast=False)
  return self
 def images(self,images):
  import torch
  with torch.inference_mode():
   inputs=self.processor(images=images,return_tensors='pt')
   return normalize(self.model.get_image_features(pixel_values=inputs.pixel_values).float().cpu().numpy())
 def text(self,texts):
  import torch
  with torch.inference_mode():
   inputs=self.processor(text=texts,return_tensors='pt',padding=True,truncation=True,max_length=77)
   return normalize(self.model.get_text_features(**inputs).float().cpu().numpy())
 def __exit__(self,*exc):
  del self.model,self.processor
  gc.collect()
  from app.influencer_engine import cleanup
  cleanup()

def reference_index(session):
 folder=ROOT/'.runtime/discovery';folder.mkdir(parents=True,exist_ok=True)
 path=folder/('index-'+cache_key()+'.npz')
 if path.exists():
  with np.load(path,allow_pickle=False) as saved:return saved['ids'],saved['images'],saved['texts']
 ids=list(ENTRIES);texts=[];images=np.zeros((len(ids),512),dtype=np.float32)
 for identifier in ids:
  item=ENTRIES[identifier]
  texts.append('A portrait of a humanoid character with '+item['features']+'.')
 text_vectors=np.concatenate([session.text(texts[i:i+4]) for i in range(0,len(texts),4)])
 for i in range(0,len(ids),4):
  batch=[];positions=[]
  for offset,identifier in enumerate(ids[i:i+4]):
   item=ENTRIES[identifier]
   if item['category']=='zodiac':continue
   p=ASSETS/item['category']/(item['key']+'.png')
   if not p.is_file():raise ValueError('Faltan imágenes del catálogo para '+item['name'])
   batch.append(reference_image(p));positions.append(i+offset)
  if batch:images[positions]=session.images(batch)
 temp=path.with_suffix('.tmp')
 with temp.open('wb') as handle:np.savez_compressed(handle,ids=np.asarray(ids),images=images,texts=text_vectors)
 temp.replace(path)
 return np.asarray(ids),images,text_vectors

def match(raw,category):
 from fastapi import HTTPException
 from app.engine import _lock
 from app.influencer_engine import face_crop
 if category not in CATEGORIES:raise ValueError('Universo desconocido.')
 if not _lock.acquire(blocking=False):raise HTTPException(409,'Hay una creación en curso. Espera a que termine para descubrir tu afinidad.')
 start=time.perf_counter()
 try:
  crop,box=face_crop(raw,reference_context=1.1)
  with ClipSession() as session:
   ids,images,texts=reference_index(session)
   query=session.images([crop])[0]
   ranked=rank(category,query,ids,images,texts)
  catalog={x['id']:x for x in public_catalog()[category]['items']}
  return dict(category=category,catalog_version=VERSION,method='local_clip_face_affinity_v2',assigned_character=catalog[ranked[0][0]] if ranked else None,photo_modified=False,query_region='face',model_repo=REPO,model_revision=REVISION,reference_sha256=hashlib.sha256(raw).hexdigest(),face_box=box,seconds=round(time.perf_counter()-start,3),suggestions=[dict(catalog[identifier],rank=i+1,similarity=round(score,6)) for i,(identifier,score) in enumerate(ranked)],notice='Afinidad visual recreativa; no identifica personalidad ni fecha de nacimiento.')
 finally:_lock.release()
