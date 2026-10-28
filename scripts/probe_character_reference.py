"""Private bounded multi-reference trial. Does not alter model weights or API defaults."""
import argparse,hashlib,json,subprocess,time,uuid,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def main():
 from app.discovery_catalog import get_inspiration,ASSETS
 from app.discovery_matcher import reference_image
 from app.influencer_engine import face_crop
 from app.engine import _lock
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--reference',type=Path,required=True);parser.add_argument('--target',required=True)
 parser.add_argument('--out',type=Path,required=True);parser.add_argument('--seed',type=int,default=8152)
 parser.add_argument('--include-traits',action='store_true')
 parser.add_argument('--clothed',action='store_true')
 args=parser.parse_args();item=get_inspiration(args.target)
 art=ASSETS/item['category']/(item['key']+'.png')
 if not art.is_file():raise ValueError('Este personaje no tiene imagen de referencia.')
 args.out.mkdir(parents=True,exist_ok=True)
 if (args.out/'result.png').exists():raise ValueError('Usa otra carpeta para conservar el resultado anterior.')
 raw=args.reference.read_bytes();crop,box=face_crop(raw,reference_context=1.85);crop.save(args.out/'reference.png')
 reference_image(art).save(args.out/'character-reference.png')
 prompt="Transform the person in image 1 into a humanoid version of the character in image 2. Preserve the person's underlying facial proportions, recognizable eyes, nose bridge, lips, original expression and apparent age. Strongly adapt the ears, skin texture and body to the character's distinctive colors, markings and shapes from image 2. Keep some original facial identity within one integrated creature. Render as a polished 3D animated film portrait with soft studio light. Show one character from the chest up."
 if args.include_traits:prompt+=' The character in image 2 is '+item['name']+'. Apply these defining traits across the transformed face, head and upper body: '+item['features']+'.'
 if args.clothed:prompt+=" Keep the person fully dressed in the shirt from image 1, covering the shoulders and torso."
 request=dict(model_id='flux_klein',output_size=[512,512],seed=args.seed,steps=4,effective_prompt=prompt)
 (args.out/'request.json').write_text(json.dumps(request,indent=2))
 provenance=dict(target=args.target,seed=args.seed,reference_sha256=hashlib.sha256(raw).hexdigest(),face_box=box,
  artwork_sha256=hashlib.sha256(art.read_bytes()).hexdigest(),weights_updated=False,
  worker_sha256=hashlib.sha256((ROOT/'scripts/probe_flux_low_memory.py').read_bytes()).hexdigest(),
  git_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
 (args.out/'provenance.json').write_text(json.dumps(provenance,indent=2))
 if not _lock.acquire(blocking=False):raise RuntimeError('Hay un trabajo activo. No se interrumpió; repite cuando termine.')
 try:
  unit='lumina-reference-'+uuid.uuid4().hex
  command=['systemd-run','--user','--scope','--quiet','--unit='+unit,'-p','MemoryMax=1800M','-p','MemorySwapMax=0','timeout','600',str(ROOT/'.runtime/modern/bin/python'),str(ROOT/'scripts/probe_flux_low_memory.py'),'--worker',str(args.out.resolve())]
  with (args.out/'worker.log').open('w') as log:
   process=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
   try:returncode=process.wait()
   finally:
    if process.poll() is None:
     subprocess.run(['systemctl','--user','stop',unit+'.scope'],timeout=10,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
     process.terminate()
     try:process.wait(timeout=5)
     except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
  (args.out/'status.json').write_text(json.dumps({'status':'failed' if returncode else 'completed','returncode':returncode,'weights_updated':False},indent=2))
  if returncode:raise RuntimeError('Prueba falló; consulta worker.log. Se conservaron los pesos y resultados anteriores.')
  print('Resultado:',args.out/'result.png',flush=True)
 finally:_lock.release()

if __name__=='__main__':main()
