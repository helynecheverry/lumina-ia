"""Download only the safetensors required by the offline portrait engine."""
import json
from pathlib import Path
from huggingface_hub import snapshot_download, hf_hub_download
ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'weights' / 'influencer'
BASE.mkdir(parents=True, exist_ok=True)
repo = 'stable-diffusion-v1-5/stable-diffusion-v1-5'
snapshot_download(repo, revision='451f4fe16113bff5a5d2269ed5ad43b0592e9a14', local_dir=BASE / 'sd15', allow_patterns=[
    'model_index.json', 'scheduler/*.json', 'tokenizer/*', 'feature_extractor/*.json',
    'text_encoder/config.json', 'text_encoder/model.fp16.safetensors',
    'unet/config.json', 'unet/diffusion_pytorch_model.fp16.safetensors',
    'vae/config.json', 'vae/diffusion_pytorch_model.fp16.safetensors',
    'safety_checker/config.json', 'safety_checker/model.fp16.safetensors',
    'README.md', 'LICENSE*'], max_workers=2)
snapshot_download('h94/IP-Adapter', revision='018e402774aeeddd60609b4ecdb7e298259dc729', local_dir=BASE / 'ip-adapter', allow_patterns=[
    'models/image_encoder/config.json', 'models/image_encoder/model.safetensors',
    'models/ip-adapter-plus-face_sd15.safetensors', 'README.md', 'LICENSE*'], max_workers=2)
print('Pesos locales listos:', BASE)
