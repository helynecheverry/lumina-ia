"""Audit private paired edit examples before training; never modifies model weights."""
import argparse,hashlib,json
from pathlib import Path
from PIL import Image

EXTENSIONS={'.png','.jpg','.jpeg','.webp'}
def scan(folder):
 result={};errors=[]
 if not folder.is_dir():return result,[f'Falta carpeta {folder.name}']
 for path in sorted(folder.iterdir()):
  if path.suffix.lower() not in EXTENSIONS:continue
  if path.stem in result:errors.append('ID duplicado: '+path.stem)
  result[path.stem]=path
 return result,errors

def audit(root):
 inputs,errors=scan(root/'reference');targets,problems=scan(root/'target');errors+=problems;pairs=[]
 for identifier in sorted(inputs.keys()|targets.keys()):
  if identifier not in inputs or identifier not in targets:
   errors.append('Par incompleto: '+identifier);continue
  caption=targets[identifier].with_suffix('.txt')
  if not caption.is_file() or not caption.read_text().strip():
   errors.append('Falta instrucción: '+identifier);continue
  values={}
  try:
   for key,path in [('reference',inputs[identifier]),('target',targets[identifier])]:
    with Image.open(path) as image:
     image=image.convert('RGB');image.load()
     values[key+'_sha256']=hashlib.sha256(str(image.size).encode()+image.tobytes()).hexdigest()
  except (OSError,ValueError):
   errors.append('Imagen inválida: '+identifier);continue
  if values['reference_sha256']==values['target_sha256']:
   errors.append('El resultado es idéntico a la entrada: '+identifier);continue
  pairs.append(dict(id=identifier,reference=str(inputs[identifier]),target=str(targets[identifier]),instruction=caption.read_text().strip(),**values))
 groups=sorted({pair['reference_sha256'] for pair in pairs})
 # Keep all edits of the same input together; never split duplicate pixels across sets.
 holdout=set(groups[::5]) if len(groups)>1 else set()
 for pair in pairs:pair['split']='validation' if pair['reference_sha256'] in holdout else 'train'
 if not pairs:errors.append('No hay pares válidos de entrada y transformación esperada.')
 if len(groups)<2:errors.append('Faltan referencias independientes para separar entrenamiento y validación.')
 return dict(data_ready=not errors,valid_pairs=len(pairs),unique_inputs=len(groups),errors=errors,pairs=pairs,
  note='La validez de archivos no certifica calidad visual, identidades variadas ni compatibilidad de hardware. No se han entrenado pesos.')

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--dataset',type=Path,required=True);parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
 report=audit(args.dataset);args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({key:value for key,value in report.items() if key!='pairs'},ensure_ascii=False,indent=2))
 raise SystemExit(0 if report['data_ready'] else 2)
if __name__=='__main__':main()
