"""Isolated local FLUX/Qwen inference. Input/output paths are created by our router."""
import json
import sys
from pathlib import Path


def write_progress(path, value, message):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'value': value, 'message': message}))
    temporary.replace(path)


def main(directory):
    import numpy as np
    import torch
    from PIL import Image, ImageOps
    from diffusers import Flux2KleinPipeline, QwenImageEditPlusPipeline
    from app.model_registry import MODELS, WEIGHTS
    from app.influencer_engine import cleanup, _check_content
    request = json.loads((directory/'request.json').read_text())
    model_id = request['model_id']
    cls = {'flux_klein': Flux2KleinPipeline, 'qwen_edit': QwenImageEditPlusPipeline}[model_id]
    status = directory/'progress.json'
    pipe = None
    try:
        write_progress(status, 5, 'Cargando el editor local')
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        pipe = cls.from_pretrained(WEIGHTS/model_id, torch_dtype=dtype,
                                  local_files_only=True, low_cpu_mem_usage=True)
        # Qwen's denoiser is larger than a 24GB card; stream groups, not the whole model.
        if model_id == 'qwen_edit':
            pipe.transformer.enable_group_offload(onload_device=torch.device('cuda'),
                offload_device=torch.device('cpu'), offload_type='block_level', num_blocks_per_group=1)
            pipe.text_encoder.to('cpu')
            # Offload the remaining modules with hooks while preserving transformer group hooks.
            from accelerate import cpu_offload
            cpu_offload(pipe.text_encoder, execution_device=torch.device('cuda'))
            pipe.vae.to('cuda')
        else:
            pipe.enable_model_cpu_offload()
        if hasattr(pipe.vae, 'enable_tiling'):
            pipe.vae.enable_tiling()
        pipe.set_progress_bar_config(disable=True)
        image = ImageOps.exif_transpose(Image.open(directory/'reference.png')).convert('RGB')
        width, height = request['output_size']
        actual_steps = 4 if model_id == 'flux_klein' else request['steps']
        def callback(pipeline, index, timestep, kwargs):
            write_progress(status, 15+int(75*(index+1)/actual_steps),
                           f'Editando tu avatar · paso {index+1}/{actual_steps}')
            return kwargs
        args = dict(image=image if model_id == 'flux_klein' else [image],
                    prompt=request['effective_prompt'], width=width, height=height,
                    num_inference_steps=actual_steps, generator=torch.Generator('cpu').manual_seed(request['seed']),
                    callback_on_step_end=callback)
        if model_id == 'flux_klein':
            args['guidance_scale'] = 1.0
        else:
            args.update(negative_prompt=request['negative_prompt'], true_cfg_scale=4.0, guidance_scale=1.0)
        with torch.inference_mode():
            result = pipe(**args).images[0]
        del pipe
        pipe = None
        cleanup()
        write_progress(status, 95, 'Comprobando el resultado')
        _check_content(np.asarray(result.convert('RGB'), dtype=np.float32)[None]/255)
        result.save(directory/'result.png')
        (directory/'result.json').write_text(json.dumps(dict(inference_steps=actual_steps,
            output_size=list(result.size), model=MODELS[model_id]['label'],
            model_revision=MODELS[model_id]['revision'], conditioning='image editing',
            source_repo=MODELS[model_id]['repo_id'],
            identity_strength_applied=False)))
    finally:
        del pipe
        cleanup()


if __name__ == '__main__':
    main(Path(sys.argv[1]))
