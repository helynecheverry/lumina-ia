"""Install one pinned pipeline; no API credentials, no automatic inference."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.model_registry import MODELS, WEIGHTS, ROOT, ADAPTER_REVISION, required_files


def install(model_id):
    from huggingface_hub import snapshot_download
    spec = MODELS[model_id]
    if spec['family'] == 'sd15':
        raise SystemExit('Usa scripts/download_influencer.py para el motor ligero.')
    target = WEIGHTS / model_id
    if spec['family'] == 'sdxl':
        patterns = required_files(model_id) + ['README.md']
    else:
        # Diffusers format only, excluding duplicate monolithic checkpoints.
        patterns = ['model_index.json', 'scheduler/*', 'tokenizer/*', 'tokenizer_2/*',
                    'processor/*', 'text_encoder/*.json', 'text_encoder/*.safetensors',
                    'text_encoder_2/*.json', 'text_encoder_2/*.safetensors',
                    'transformer/*.json', 'transformer/*.safetensors',
                    'vae/*.json', 'vae/*.safetensors', 'README.md', 'LICENSE*']
    snapshot_download(spec['repo_id'], revision=spec['revision'], local_dir=target,
                      allow_patterns=patterns, max_workers=1)
    if spec['family'] == 'sdxl':
        snapshot_download('h94/IP-Adapter', revision=ADAPTER_REVISION,
            local_dir=ROOT/'weights/influencer/ip-adapter',
            allow_patterns=['sdxl_models/ip-adapter-plus-face_sdxl_vit-h.safetensors',
                            'models/image_encoder/config.json', 'models/image_encoder/model.safetensors'], max_workers=1)
    files = {}
    for path in sorted(target.rglob('*')):
        if not path.is_file() or '.cache' in path.parts or path.name == 'install-manifest.json':
            continue
        digest = hashlib.sha256()
        with path.open('rb') as handle:
            for block in iter(lambda: handle.read(8*1024*1024), b''):
                digest.update(block)
        files[str(path.relative_to(target))] = {'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}
    manifest = dict(model_id=model_id, repo_id=spec['repo_id'], revision=spec['revision'], files=files)
    (target/'install-manifest.json').write_text(json.dumps(manifest, indent=2))
    print('Instalado:', model_id, target, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model_id', choices=[key for key in MODELS if key != 'portrait_sd15'])
    install(parser.parse_args().model_id)
