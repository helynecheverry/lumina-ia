"""Pinned, compatible local pipelines. Readiness never means 'benchmark passed'."""
import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = ROOT / 'weights' / 'studio'
DEFAULT_MODEL = 'portrait_sd15'
MODELS = {
    'portrait_sd15': dict(label='Retrato ligero', family='sd15',
        description='Realistic Vision / DreamShaper con referencia facial. Optimizado para este equipo.',
        repo_id='SG161222/Realistic_Vision_V5.1_noVAE',
        revision='1e9f017a7b1eaefb63a1900ea6c5953d2739fd21',
        license='CreativeML OpenRAIL-M', resolutions={'square': [512, 512], 'portrait': [512, 768]},
        min_vram_gb=3, min_ram_gb=6),
    'portrait_sdxl': dict(label='Retrato editorial XL', family='sdxl',
        description='RealVisXL 5.0 + referencia facial. Especializado en fotografía; para anime o plastilina elige Retrato ligero.',
        repo_id='SG161222/RealVisXL_V5.0', revision='ac93e0dda1f6d448cae19bbfab8c5e720a5e48bc',
        license='OpenRAIL++', resolutions={'square': [768, 768], 'portrait': [768, 1024]},
        min_vram_gb=3.5, min_ram_gb=6),
    'flux_klein': dict(label='Creación y edición · FLUX', family='flux',
        description='FLUX.2 klein 4B: transforma tu referencia mediante instrucciones.',
        repo_id='black-forest-labs/FLUX.2-klein-4B', revision='e7b7dc27f91deacad38e78976d1f2b499d76a294',
        license='Apache-2.0', resolutions={'square': [1024, 1024], 'portrait': [768, 1024]},
        min_vram_gb=13, min_ram_gb=16, fixed_steps=4),
    'qwen_edit': dict(label='Edición de apariencia · Qwen', family='qwen',
        description='Qwen Image Edit 2511: cambia vestuario, fondo y estilo desde tu imagen.',
        repo_id='Qwen/Qwen-Image-Edit-2511', revision='6f3ccc0b56e431dc6a0c2b2039706d7d26f22cb9',
        license='Apache-2.0', resolutions={'square': [1024, 1024], 'portrait': [768, 1024]},
        min_vram_gb=24, min_ram_gb=64),
}
ADAPTER_REVISION = '018e402774aeeddd60609b4ecdb7e298259dc729'


def verified_low_memory_flux(hw):
    if hw['vram_gb'] >= MODELS['flux_klein']['min_vram_gb']:
        return False
    try:
        report=json.loads((ROOT/'artifacts/modern-probes/flux-klein-low-memory.json').read_text())
        return (report.get('status')=='completed' and report.get('revision')==MODELS['flux_klein']['revision']
                and report.get('gpu')==hw.get('gpu') and bool(hw.get('gpu')))
    except (ValueError,OSError):
        return False


def resolution_options(model_id,hw=None):
    if model_id=='flux_klein' and verified_low_memory_flux(hw or hardware()):
        return {'square':[512,512],'portrait':[512,768]}
    return MODELS[model_id]['resolutions']


def hardware():
    import torch
    cuda = torch.cuda.is_available()
    ram = os.sysconf('SC_PHYS_PAGES') * os.sysconf('SC_PAGE_SIZE') / 1024 ** 3
    return dict(cuda=cuda, gpu=torch.cuda.get_device_name(0) if cuda else None,
                vram_gb=round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2) if cuda else 0,
                ram_gb=round(ram, 2))


def required_files(model_id):
    family = MODELS[model_id]['family']
    if family == 'sd15':
        return []
    if family == 'sdxl':
        paths = ['model_index.json', 'install-manifest.json', 'scheduler/scheduler_config.json',
                 'unet/config.json', 'unet/diffusion_pytorch_model.fp16.safetensors',
                 'vae/config.json', 'vae/diffusion_pytorch_model.fp16.safetensors']
        for name in ['text_encoder', 'text_encoder_2']:
            paths += [name+'/config.json', name+'/model.fp16.safetensors']
        for name in ['tokenizer', 'tokenizer_2']:
            paths += [name+'/'+f for f in ['vocab.json', 'merges.txt', 'tokenizer_config.json', 'special_tokens_map.json']]
        return paths
    # The installer writes a manifest only after every selected HF download succeeds.
    return ['model_index.json', 'install-manifest.json']


def model_status(model_id, hw=None):
    if model_id not in MODELS:
        raise ValueError('Motor desconocido')
    spec = MODELS[model_id]
    result = dict(spec, id=model_id, external_uploads=False)
    if spec['family'] == 'sd15':
        from app.influencer_engine import readiness
        old = readiness()
        result.update(installed=old['weights_ready'], ready=old['ready'],
                      reason='' if old['ready'] else 'Faltan pesos del motor ligero o GPU CUDA.',
                      tested=old['ready'], missing_files=old['missing_files'])
        return result
    hw = hw or hardware()
    low_flux = model_id=='flux_klein' and verified_low_memory_flux(hw)
    if low_flux:
        result.update(label='FLUX · Memoria reducida',min_vram_gb=3.5,min_ram_gb=6,
            description='Edición con tu foto · modo experimental probado en esta GPU. Cuatro pasos y carga por etapas.',
            resolutions=resolution_options(model_id,hw),experimental=True)
    root = WEIGHTS / model_id
    missing = [name for name in required_files(model_id) if not (root / name).is_file()]
    if (root/'install-manifest.json').is_file():
        try:
            manifest = json.loads((root/'install-manifest.json').read_text())
            if manifest.get('revision') != spec['revision'] or not manifest.get('files'):
                missing.append('manifest: revisión incorrecta')
            for name, details in manifest.get('files', {}).items():
                file = root / name
                if not file.is_file() or file.stat().st_size != details['bytes']:
                    missing.append(name)
        except (ValueError, KeyError, OSError):
            missing.append('manifest: inválido')
    if spec['family'] == 'sdxl':
        adapter = ROOT / 'weights/influencer/ip-adapter'
        for name in ['sdxl_models/ip-adapter-plus-face_sdxl_vit-h.safetensors',
                     'models/image_encoder/model.safetensors', 'models/image_encoder/config.json']:
            if not (adapter / name).is_file():
                missing.append('ip-adapter/' + name)
    # All outputs pass the same local content check before they are stored.
    for name in ['sd15/safety_checker/config.json', 'sd15/safety_checker/model.fp16.safetensors',
                 'sd15/feature_extractor/preprocessor_config.json']:
        if not (ROOT/'weights/influencer'/name).is_file():
            missing.append('shared/'+name)
    reasons = []
    if not hw['cuda']:
        reasons.append('Se requiere una GPU CUDA.')
    if hw['vram_gb'] < result['min_vram_gb'] or hw['ram_gb'] < result['min_ram_gb']:
        reasons.append(f"Perfil configurado: {result['min_vram_gb']} GB VRAM y {result['min_ram_gb']} GB RAM; este equipo no alcanza ese perfil.")
    if missing:
        reasons.append('Pesos pendientes de instalación.')
    if spec['family'] in ('flux', 'qwen'):
        runtime = ROOT / '.runtime/modern/bin/python'
        if not runtime.is_file() or not (runtime.parent.parent/'validated.json').is_file():
            reasons.append('Falta el entorno de los motores modernos.')
        if low_flux and (not shutil.which('systemd-run') or not Path(f'/run/user/{os.getuid()}/bus').exists()):
            reasons.append('Falta el aislador de memoria del modo experimental.')
    report = ROOT / 'artifacts/multi-model' / (model_id + '-validation.json')
    tested = low_flux
    if report.is_file():
        try:
            saved = json.loads(report.read_text())
            tested = tested or (saved.get('status') == 'completed' and saved.get('revision') == spec['revision'])
        except (ValueError, OSError):
            pass
    result.update(installed=not missing, ready=not reasons, tested=tested, missing_files=missing,
                  reason=' '.join(reasons), low_memory=low_flux or (spec['family'] == 'sdxl' and hw['vram_gb'] < 8),
                  install_command=f'python scripts/install_studio_model.py {model_id}')
    return result


def catalog():
    hw = hardware()
    models={key:model_status(key,hw) for key in MODELS}
    return {'default_model': 'flux_klein' if models['flux_klein']['ready'] else DEFAULT_MODEL,
            'hardware': hw, 'models':models}


def validate_selection(model_id, framing='square'):
    if model_id not in MODELS:
        raise ValueError('Motor desconocido')
    resolutions=resolution_options(model_id)
    if framing not in resolutions:
        raise ValueError('Encuadre inválido')
    return resolutions[framing]
