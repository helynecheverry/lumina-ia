"""Additional offline models for generation recipe 2.0."""
from pathlib import Path
from huggingface_hub import snapshot_download
root=Path(__file__).resolve().parents[1]/'weights/influencer'
for repo, revision, folder, patterns in [
 ('Helsinki-NLP/opus-mt-es-en','c96e2c5399ebfae4fc43d9669556b9afa74bb69d','translator',['*.json','*.spm','pytorch_model.bin','README.md']),
 ('Lykon/dreamshaper-8','a7e52b98680b1ba8ff7bce97c7f9f2e2e5337917','dreamshaper',['unet/config.json','unet/diffusion_pytorch_model.fp16.safetensors','README.md']),
 ('stabilityai/sd-vae-ft-mse','31f26fdeee1355a5c34592e401dd41e45d25a493','vae-mse',['config.json','diffusion_pytorch_model.safetensors','README.md']),
]:
 snapshot_download(repo, revision=revision,local_dir=root/folder,allow_patterns=patterns,max_workers=2)
 print(folder,'ready')
