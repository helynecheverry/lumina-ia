"""RealVisXL + compatible IP-Adapter with staged encoders and disk offload.

The small-GPU path trades latency and disk I/O for bounded GPU residency.
No remote inference or model download occurs in this module.
"""
import time
import types

import cv2
import numpy as np
import torch

from app import engine
from app.influencer_engine import (cleanup, face_crop, _encode_face, _check_content,
                                   _stable_conv_forward, GenerationCancelled, MODEL_DIR)
from app.model_registry import WEIGHTS, MODELS, ROOT, validate_selection
from app.prompting import compile_studio_prompt

MODEL_ID = 'portrait_sdxl'
PATH = WEIGHTS / MODEL_ID


def encode_text(positive, negative):
    """Encode both CLIP contexts in full, one encoder resident at a time."""
    from transformers import CLIPTokenizer, CLIPTextModel, CLIPTextModelWithProjection
    tokenizers = [CLIPTokenizer.from_pretrained(PATH / folder, local_files_only=True)
                  for folder in ('tokenizer', 'tokenizer_2')]
    contexts = []
    max_chunks = 1
    for tokenizer in tokenizers:
        pair = []
        for text in (positive, negative):
            ids = tokenizer(text, truncation=False, add_special_tokens=False).input_ids
            size = tokenizer.model_max_length - 2
            chunks = [ids[i:i+size] for i in range(0, len(ids), size)] or [[]]
            pair.append(chunks)
            max_chunks = max(max_chunks, len(chunks))
        contexts.append(pair)
    if max_chunks > 4:
        raise ValueError('Reduce la descripción: supera el contexto admitido')
    embeddings, pooled = [], None
    for index, (tokenizer, pair) in enumerate(zip(tokenizers, contexts)):
        encoder = None
        try:
            cls = CLIPTextModel if index == 0 else CLIPTextModelWithProjection
            encoder = cls.from_pretrained(PATH / ('text_encoder' if index == 0 else 'text_encoder_2'),
                variant='fp16', torch_dtype=torch.float16, local_files_only=True,
                low_cpu_mem_usage=True).to('cuda')
            per_direction, per_pool = [], []
            for chunks in pair:
                hidden, pools = [], []
                for chunk in range(max_chunks):
                    content = chunks[chunk] if chunk < len(chunks) else []
                    sequence = [tokenizer.bos_token_id] + content + [tokenizer.eos_token_id]
                    sequence += [tokenizer.pad_token_id] * (tokenizer.model_max_length - len(sequence))
                    result = encoder(torch.tensor([sequence], device='cuda'), output_hidden_states=True)
                    hidden.append(result.hidden_states[-2].cpu())
                    if index == 1:
                        pools.append(result.text_embeds.cpu())
                per_direction.append(torch.cat(hidden, dim=1))
                if pools:
                    per_pool.append(torch.stack(pools).mean(0))
            embeddings.append(per_direction)
            if index == 1:
                pooled = per_pool
        finally:
            del encoder
            cleanup()
    return (torch.cat([item[0] for item in embeddings], dim=-1),
            torch.cat([item[1] for item in embeddings], dim=-1), pooled[0], pooled[1], max_chunks)


def diffuse(face, encoded, seed, strength, steps, size, progress, cancelled):
    from accelerate import disk_offload
    from diffusers import StableDiffusionXLPipeline, DPMSolverMultistepScheduler, UNet2DConditionModel
    pipe, unet = None, None
    try:
        progress(12, 'Cargando RealVisXL · la primera carga puede tardar')
        unet = UNet2DConditionModel.from_pretrained(PATH/'unet', variant='fp16',
            torch_dtype=torch.float16, local_files_only=True, low_cpu_mem_usage=True, use_safetensors=True)
        scheduler = DPMSolverMultistepScheduler.from_pretrained(PATH/'scheduler', local_files_only=True,
            use_karras_sigmas=True, euler_at_final=True)
        pipe = StableDiffusionXLPipeline(vae=None, text_encoder=None, text_encoder_2=None,
            tokenizer=None, tokenizer_2=None, unet=unet, scheduler=scheduler, add_watermarker=False)
        pipe.load_ip_adapter(str(MODEL_DIR/'ip-adapter'), subfolder='sdxl_models',
            weight_name='ip-adapter-plus-face_sdxl_vit-h.safetensors',
            image_encoder_folder=None, local_files_only=True)
        pipe.set_ip_adapter_scale(strength * .55)
        if 'GTX 16' in torch.cuda.get_device_name():
            for module in unet.modules():
                if isinstance(module, torch.nn.Conv2d):
                    module.forward = types.MethodType(_stable_conv_forward, module)
        low_memory = torch.cuda.get_device_properties(0).total_memory < 8*1024**3
        if low_memory:
            # Revision-scoped cache: never reuse tensors from another checkpoint/adapter.
            cache = ROOT/'.runtime/offload'/('sdxl-'+MODELS[MODEL_ID]['revision'][:12]+'-ip-plus-face-v1')
            cache.mkdir(parents=True, exist_ok=True)
            disk_offload(unet, offload_dir=cache, execution_device=torch.device('cuda:0'), offload_buffers=True)
        else:
            pipe.to('cuda')
        cleanup()
        pipe.set_progress_bar_config(disable=True)
        def callback(pipeline, index, timestep, kwargs):
            if cancelled():
                raise GenerationCancelled()
            if not torch.isfinite(kwargs['latents']).all():
                raise ValueError('El motor XL produjo valores no válidos; prueba otro encuadre o motor.')
            fraction = (index+1)/steps
            pipeline.set_ip_adapter_scale(strength * (.7 if fraction < .2 else 1.0))
            progress(20+int(65*fraction), f'Retrato XL · paso {index+1}/{steps}')
            return kwargs
        if cancelled():
            raise GenerationCancelled()
        pos, neg, pool, neg_pool, _ = encoded
        # No vae in this phase: decode separately after releasing the large denoiser.
        result = pipe(prompt_embeds=pos.to('cuda'), negative_prompt_embeds=neg.to('cuda'),
            pooled_prompt_embeds=pool.to('cuda'), negative_pooled_prompt_embeds=neg_pool.to('cuda'),
            ip_adapter_image_embeds=[face], guidance_scale=5.5, num_inference_steps=steps,
            width=size[0], height=size[1], original_size=(1024, 1024),
            target_size=(size[1], size[0]), output_type='latent',
            generator=torch.Generator('cpu').manual_seed(seed), callback_on_step_end=callback).images.cpu()
        return result, 'disk_offload' if low_memory else 'cuda'
    finally:
        del pipe, unet
        cleanup()


def decode(latents):
    from diffusers import AutoencoderKL
    vae = None
    try:
        vae = AutoencoderKL.from_pretrained(PATH/'vae', variant='fp16', torch_dtype=torch.float32,
            use_safetensors=True, low_cpu_mem_usage=True, local_files_only=True).to('cuda')
        vae.enable_tiling()
        vae.tile_sample_min_size = 256
        vae.tile_latent_min_size = 32
        value = vae.decode(latents.to(device='cuda', dtype=torch.float32)/vae.config.scaling_factor).sample
        if not torch.isfinite(value).all():
            raise ValueError('No se pudo revelar el retrato XL.')
        return (value/2+.5).clamp(0, 1).permute(0, 2, 3, 1).cpu().numpy()
    finally:
        del vae
        cleanup()


def generate(raw, preset='editorial', prompt='', seed=42, identity_strength=.6, steps=32,
             progress=lambda *args: None, cancelled=lambda: False, character_type='natural', framing='square', appearance=None, inspiration_id=''):
    size = validate_selection(MODEL_ID, framing)
    start = time.perf_counter()
    with engine._lock, torch.inference_mode():
        engine.unload_engine()
        torch.backends.cudnn.benchmark = False
        torch.set_num_threads(2)
        cleanup()
        try:
            def checkpoint(value, message):
                if cancelled():
                    raise GenerationCancelled()
                progress(value, message)
            checkpoint(1, 'Interpretando tu retrato editorial')
            recipe = compile_studio_prompt(preset, prompt, character_type=character_type, model_id=MODEL_ID, framing=framing, appearance=appearance, inspiration_id=inspiration_id)
            identity_strength = max(recipe['identity_min'], min(identity_strength, recipe['identity_max']))
            crop, box = face_crop(raw, reference_context=recipe['reference_context'])
            checkpoint(3, 'Preparando los dos codificadores de texto XL')
            encoded = encode_text(recipe['effective_prompt'], recipe['negative_prompt'])
            checkpoint(8, 'Leyendo tu referencia facial')
            face = _encode_face(crop)
            latents, mode = diffuse(face, encoded, seed, identity_strength, steps, size, progress, cancelled)
            del face, encoded
            cleanup()
            checkpoint(88, 'Revelando el retrato XL')
            images = decode(latents)
            checkpoint(95, 'Comprobando el resultado')
            _check_content(images)
            checkpoint(98, 'Guardando tu retrato')
            output = engine.encode(cv2.cvtColor((images[0]*255).round().astype(np.uint8), cv2.COLOR_RGB2BGR))
            return output, dict(seconds=round(time.perf_counter()-start, 3), device='cuda', face_box=box,
                applied_identity_strength=identity_strength, output_size=size, model='RealVisXL 5.0 + IP-Adapter Plus Face SDXL',
                model_revision=MODELS[MODEL_ID]['revision'], source_repo=MODELS[MODEL_ID]['repo_id'],
                identity_adapter='ip-adapter-plus-face_sdxl_vit-h', memory_mode=mode,
                **recipe)
        finally:
            cleanup()
