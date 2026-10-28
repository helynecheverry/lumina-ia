"""Optional photorealistic SD 1.5 fine-tune, compatible with the existing adapter."""
from pathlib import Path
from huggingface_hub import snapshot_download
root = Path(__file__).resolve().parents[1] / 'weights' / 'influencer' / 'realistic-vision'
snapshot_download('SG161222/Realistic_Vision_V5.1_noVAE', revision='1e9f017a7b1eaefb63a1900ea6c5953d2739fd21',
    local_dir=root, allow_patterns=['unet/config.json', 'unet/diffusion_pytorch_model.safetensors', 'README.md'], max_workers=1)
print('Realistic Vision disponible:', root)
