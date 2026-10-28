"""Install the pinned local CLIP matcher; no inference and no user photo upload."""
from pathlib import Path
from huggingface_hub import snapshot_download
ROOT=Path(__file__).resolve().parents[1]
REPO='openai/clip-vit-base-patch32'
REVISION='3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268'
if __name__=='__main__':
    path=snapshot_download(REPO,revision=REVISION,local_dir=ROOT/'weights/discovery/clip',allow_patterns=['config.json','preprocessor_config.json','pytorch_model.bin','merges.txt','vocab.json','tokenizer.json','tokenizer_config.json','special_tokens_map.json','README.md'],max_workers=2)
    print('CLIP instalado:',path)
