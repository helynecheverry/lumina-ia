"""Offline portrait generation with SD 1.5 + IP-Adapter Plus Face.

This is an independent local alternative, not Higgsfield's private model.
The vision encoder is released before diffusion to fit a 4 GB GPU.
"""
import gc
import ctypes
import sys
import types
import os
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image

from app import engine

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / 'weights' / 'influencer'
from app.style_catalog import PRESETS, RECIPE_VERSION
from app.prompting import compile_studio_prompt, encode_complete_prompt

REQUIRED_FILES = (
    'sd15/model_index.json', 'sd15/unet/diffusion_pytorch_model.fp16.safetensors',
    'sd15/text_encoder/model.fp16.safetensors', 'sd15/vae/diffusion_pytorch_model.fp16.safetensors',
    'sd15/safety_checker/model.fp16.safetensors',
    'ip-adapter/models/image_encoder/model.safetensors',
    'ip-adapter/models/ip-adapter-plus-face_sd15.safetensors',
    'dreamshaper/unet/diffusion_pytorch_model.fp16.safetensors',
    'translator/pytorch_model.bin', 'translator/source.spm', 'translator/target.spm',
    'vae-mse/diffusion_pytorch_model.safetensors',
)


class GenerationCancelled(Exception):
    pass


def photorealistic_available():
    return (MODEL_DIR / 'realistic-vision/unet/diffusion_pytorch_model.safetensors').is_file()


def readiness():
    missing = [name for name in REQUIRED_FILES if not (MODEL_DIR / name).is_file()]
    return {'ready': not missing and torch.cuda.is_available(), 'weights_ready': not missing,
            'device': 'cuda' if torch.cuda.is_available() else 'cpu', 'missing_files': missing,
            'provider': 'local', 'model': ('Realistic Vision 5.1 (SD 1.5)' if photorealistic_available() else 'Stable Diffusion 1.5') + ' + IP-Adapter Plus Face',
            'base_model': 'SG161222/Realistic_Vision_V5.1_noVAE' if photorealistic_available() else 'stable-diffusion-v1-5/stable-diffusion-v1-5',
            'identity_adapter': 'h94/IP-Adapter · ip-adapter-plus-face_sd15',
            'external_uploads': False, 'resolution': [512, 512], 'recipe_version': RECIPE_VERSION,
            'translator_ready': (MODEL_DIR / 'translator/pytorch_model.bin').is_file(),
            'art_model_ready': (MODEL_DIR / 'dreamshaper/unet/diffusion_pytorch_model.fp16.safetensors').is_file()}


def face_crop(raw, reference_context=1.65):
    image = engine.decode(raw)
    height, width = image.shape[:2]
    factor = min(1., 1024 / max(width, height))
    small = cv2.resize(image, (round(width * factor), round(height * factor)))
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = cascade.detectMultiScale(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), scaleFactor=1.1,
                                     minNeighbors=5, minSize=(40, 40))
    if len(faces) == 0:
        raise ValueError('No se detectó un rostro frontal. Acerca la cámara, mejora la luz y evita gafas oscuras.')
    if len(faces) > 1:
        raise ValueError('Usa una foto de una sola persona o recórtala para dejar un único rostro.')
    x, y, w, h = [int(v / factor) for v in faces[0]]
    size = int(max(w, h) * reference_context)
    cx, cy = x + w // 2, y + h // 2
    left, top = max(0, cx - size // 2), max(0, cy - size // 2)
    right, bottom = min(width, left + size), min(height, top + size)
    crop = Image.fromarray(cv2.cvtColor(image[top:bottom, left:right], cv2.COLOR_BGR2RGB))
    return crop, {'x': x, 'y': y, 'width': w, 'height': h}


def cleanup():
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    if sys.platform.startswith('linux'):
        ctypes.CDLL('libc.so.6').malloc_trim(0)


def _encode_face(crop):
    from transformers import CLIPImageProcessor, CLIPVisionModelWithProjection
    encoder = None
    try:
        encoder = CLIPVisionModelWithProjection.from_pretrained(
            MODEL_DIR / 'ip-adapter/models/image_encoder', torch_dtype=torch.float16,
            local_files_only=True, low_cpu_mem_usage=True, device_map={'': 0})
        pixels = CLIPImageProcessor()(images=crop, return_tensors='pt').pixel_values.to('cuda', dtype=torch.float16)
        positive = encoder(pixels, output_hidden_states=True).hidden_states[-2]
        negative = encoder(torch.zeros_like(pixels), output_hidden_states=True).hidden_states[-2]
        embeddings = torch.cat([negative, positive]).unsqueeze(1).cpu()
        if not torch.isfinite(embeddings).all():
            raise RuntimeError('El codificador produjo valores no válidos')
        return embeddings
    finally:
        del encoder
        cleanup()


def _stable_conv_forward(module, inputs):
    """Keep compact FP16 weights but compute convolutions in FP32 on GTX 16xx."""
    result = module._conv_forward(inputs.float(), module.weight.float(),
                                  module.bias.float() if module.bias is not None else None)
    return result.to(inputs.dtype)


def _diffuse(embeddings, direction, seed, identity_strength, steps, progress, cancelled, photographic=True, negative_prompt=None, output_size=(512, 512)):
    from diffusers import StableDiffusionPipeline, DPMSolverMultistepScheduler, UNet2DConditionModel
    pipe = None
    try:
        # Decode and safety are separate phases below, each with its own weights.
        # They are always executed before returning a viewable result.
        components = {}
        if photographic and photorealistic_available():
            components['unet'] = UNet2DConditionModel.from_pretrained(
                MODEL_DIR / 'realistic-vision/unet', torch_dtype=torch.float16,
                use_safetensors=True, local_files_only=True, low_cpu_mem_usage=True, device_map={'': 0})
        if not photographic and (MODEL_DIR / 'dreamshaper/unet/diffusion_pytorch_model.fp16.safetensors').is_file():
            components['unet'] = UNet2DConditionModel.from_pretrained(
                MODEL_DIR / 'dreamshaper/unet', variant='fp16', torch_dtype=torch.float16,
                use_safetensors=True, local_files_only=True, low_cpu_mem_usage=True, device_map={'': 0})
        if not components:
            components['unet'] = UNet2DConditionModel.from_pretrained(MODEL_DIR/'sd15/unet',
                variant='fp16',torch_dtype=torch.float16,use_safetensors=True,
                local_files_only=True,low_cpu_mem_usage=True,device_map={'':0})
        pipe = StableDiffusionPipeline.from_pretrained(
            MODEL_DIR / 'sd15', torch_dtype=torch.float16, variant='fp16',
            use_safetensors=True, local_files_only=True, low_cpu_mem_usage=True,
            vae=None, safety_checker=None, feature_extractor=None, requires_safety_checker=False, **components)
        del components
        pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config, use_karras_sigmas=True)
        pipe.load_ip_adapter(str(MODEL_DIR / 'ip-adapter'), subfolder='models',
                             weight_name='ip-adapter-plus-face_sd15.safetensors',
                             image_encoder_folder=None, local_files_only=True)
        pipe.set_ip_adapter_scale(identity_strength * .45)
        pipe.to('cuda')
        if 'GTX 16' in torch.cuda.get_device_name():
            for module in pipe.unet.modules():
                if isinstance(module, torch.nn.Conv2d):
                    module.forward = types.MethodType(_stable_conv_forward, module)
        if os.getenv('LOCAL_MODEL_DIAGNOSTICS') == '1':
            def diagnostic(name):
                def check(module, inputs, output):
                    if isinstance(output, torch.Tensor) and not torch.isfinite(output).all():
                        raise RuntimeError('Non-finite module: ' + name)
                return check
            for prefix, network in [('unet', pipe.unet), ('text', pipe.text_encoder)]:
                for name, module in network.named_modules():
                    if isinstance(module, (torch.nn.Conv2d, torch.nn.Linear, torch.nn.LayerNorm, torch.nn.GroupNorm)):
                        module.register_forward_hook(diagnostic(prefix + '.' + name))
        pipe.set_progress_bar_config(disable=True)
        def callback(pipeline, index, timestep, kwargs):
            if not torch.isfinite(kwargs['latents']).all():
                raise RuntimeError(f'Valores no válidos en el paso {index + 1}')
            if cancelled():
                raise GenerationCancelled()
            fraction = (index + 1) / steps
            influence = .65 if fraction < .2 else (1. if fraction < .8 else .75)
            pipeline.set_ip_adapter_scale(identity_strength * influence)
            progress(15 + int(70 * fraction), f'Creando imagen · paso {index + 1}/{steps}')
            return kwargs
        positive_embeds, negative_embeds, chunks = encode_complete_prompt(pipe, direction, negative_prompt)
        latents = pipe(prompt_embeds=positive_embeds, negative_prompt_embeds=negative_embeds,
                       ip_adapter_image_embeds=[embeddings],
                       num_inference_steps=steps, guidance_scale=7. if photographic else 8., width=output_size[0], height=output_size[1],
                       generator=torch.Generator(device='cpu').manual_seed(seed),
                       output_type='latent', callback_on_step_end=callback).images.cpu()
        if not torch.isfinite(latents).all():
            raise RuntimeError('La difusión produjo valores no válidos')
        return latents
    finally:
        del pipe
        cleanup()


def _decode_latents(latents):
    from diffusers import AutoencoderKL
    vae = None
    try:
        # GTX 16xx can produce NaNs with a half precision VAE. Decode in float32.
        enhanced = (MODEL_DIR / 'vae-mse/diffusion_pytorch_model.safetensors').is_file()
        vae = AutoencoderKL.from_pretrained(MODEL_DIR / 'vae-mse' if enhanced else MODEL_DIR / 'sd15/vae', variant=None if enhanced else 'fp16',
            torch_dtype=torch.float32, use_safetensors=True, local_files_only=True,
            low_cpu_mem_usage=True).to('cuda')
        vae.enable_tiling()
        vae.tile_sample_min_size = 256
        vae.tile_latent_min_size = 32
        image = vae.decode(latents.to('cuda', dtype=torch.float32) / vae.config.scaling_factor).sample
        if not torch.isfinite(image).all():
            raise RuntimeError('El decodificador produjo valores no válidos')
        return (image / 2 + .5).clamp(0, 1).permute(0, 2, 3, 1).cpu().float().numpy()
    finally:
        del vae
        cleanup()


def _check_content(images):
    from diffusers.pipelines.stable_diffusion.safety_checker import StableDiffusionSafetyChecker
    from transformers import CLIPImageProcessor
    checker = None
    try:
        checker = StableDiffusionSafetyChecker.from_pretrained(MODEL_DIR / 'sd15/safety_checker',
            variant='fp16', torch_dtype=torch.float32, use_safetensors=True,
            local_files_only=True, low_cpu_mem_usage=True, device_map={'':0})
        processor = CLIPImageProcessor.from_pretrained(MODEL_DIR / 'sd15/feature_extractor', local_files_only=True)
        previews = [Image.fromarray((item * 255).round().astype(np.uint8)) for item in images]
        clip_input = processor(images=previews, return_tensors='pt').pixel_values.to('cuda')
        _, flagged = checker(images=images, clip_input=clip_input)
        if any(flagged):
            raise ValueError('El filtro de contenido bloqueó este resultado. Prueba otro estilo o descripción.')
    finally:
        del checker
        cleanup()


def generate(raw, preset='editorial', prompt='', seed=42, identity_strength=.6, steps=32,
             progress=lambda *args: None, cancelled=lambda: False, character_type='natural', output_size=(512, 512), appearance=None, inspiration_id=''):
    if not readiness()['ready']:
        raise RuntimeError('Faltan pesos locales o una GPU CUDA. Ejecuta scripts/download_influencer.py.')
    start = time.perf_counter()
    with engine._lock, torch.inference_mode():
        engine.unload_engine()
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.benchmark_limit = 1
        cleanup()
        try:
            def checkpoint(value, message):
                if cancelled():
                    raise GenerationCancelled()
                progress(value, message)
            checkpoint(1, 'Interpretando tus instrucciones')
            recipe = compile_studio_prompt(preset, prompt, character_type=character_type,
                framing='portrait' if output_size[1] > output_size[0] else 'square', appearance=appearance, inspiration_id=inspiration_id)
            identity_strength = max(recipe['identity_min'], min(identity_strength, recipe['identity_max']))
            crop, box = face_crop(raw, reference_context=recipe['reference_context'])
            cleanup()
            checkpoint(3, 'Leyendo tu referencia')
            embeddings = _encode_face(crop)
            cleanup()
            checkpoint(10, 'Preparando el estudio local')
            latents = _diffuse(embeddings, recipe['effective_prompt'], seed, identity_strength, steps, progress, cancelled,
                               photographic=recipe['backbone'] == 'photo', negative_prompt=recipe['negative_prompt'], output_size=output_size)
            cleanup()
            checkpoint(88, 'Revelando tu retrato')
            images = _decode_latents(latents)
            cleanup()
            checkpoint(95, 'Comprobando el resultado')
            _check_content(images)
            checkpoint(98, 'Guardando tu creación')
            output = engine.encode(cv2.cvtColor((images[0] * 255).round().astype(np.uint8), cv2.COLOR_RGB2BGR))
            if recipe['backbone'] == 'art':
                source_repo, source_revision = 'Lykon/dreamshaper-8', 'a7e52b98680b1ba8ff7bce97c7f9f2e2e5337917'
            elif photorealistic_available():
                source_repo, source_revision = 'SG161222/Realistic_Vision_V5.1_noVAE', '1e9f017a7b1eaefb63a1900ea6c5953d2739fd21'
            else:
                source_repo, source_revision = 'stable-diffusion-v1-5/stable-diffusion-v1-5', '451f4fe16113bff5a5d2269ed5ad43b0592e9a14'
            return output, {'seconds': round(time.perf_counter() - start, 3), 'device': 'cuda',
                            'face_box': box, 'output_size': list(output_size),
                            'applied_identity_strength': identity_strength,
                            'model': 'DreamShaper 8 + IP-Adapter Plus Face' if recipe['backbone'] == 'art' else readiness()['model'],
                            'source_repo': source_repo, 'model_revision': source_revision,
                            'identity_adapter': 'ip-adapter-plus-face_sd15',
                            'conditioning': 'scheduled image influence', 'decoder': 'sd-vae-ft-mse', **recipe}
        finally:
            cleanup()
