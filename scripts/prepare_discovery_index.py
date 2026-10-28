"""Build local character embeddings once, while the shared model lock is free."""
import sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.engine import _lock
from app.discovery_matcher import ClipSession,reference_index
if __name__=='__main__':
    start=time.monotonic()
    with _lock,ClipSession() as session:
        ids,images,texts=reference_index(session)
    print('Índice preparado:',len(ids),'personajes en',round(time.monotonic()-start,2),'s',flush=True)
