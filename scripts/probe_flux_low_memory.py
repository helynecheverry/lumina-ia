"""Bounded experimental FLUX inference; run only while the studio GPU is idle.

Launch with systemd MemoryMax so an unsuccessful attempt cannot consume all RAM.
This is an experiment, not a claim that the standard pipeline fits a 4GB GPU.
"""
import gc
import json
import sys
import time
import types
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def run(directory=None):
    import numpy as np
    import torch
    import torch.nn.functional as functional
    from accelerate import disk_offload
    from transformers import Qwen3Model, Qwen2TokenizerFast
    from diffusers import Flux2KleinPipeline, Flux2Transformer2DModel, AutoencoderKLFlux2, FlowMatchEulerDiscreteScheduler
    from PIL import Image
    from app.influencer_engine import cleanup, _stable_conv_forward, _check_content
    from app.model_registry import WEIGHTS, MODELS

    output=ROOT/'artifacts/modern-probes';output.mkdir(parents=True,exist_ok=True)
    request=json.loads((directory/'request.json').read_text()) if directory else {}
    class LowMemoryFluxPipeline(Flux2KleinPipeline):
        @property
        def _execution_device(self):
            # The denoiser has meta parameters under disk_offload; that is not
            # the execution device for latents or the resident image codec.
            return torch.device('cuda:0')
    path=WEIGHTS/'flux_klein'
    cache=ROOT/'.runtime/offload'/('flux-klein-'+MODELS['flux_klein']['revision'][:12])
    start=time.perf_counter()
    def log(stage,progress=None):
        print(stage,round(time.perf_counter()-start,1),flush=True)
        if directory and progress is not None:
            temporary=directory/'progress.tmp'
            temporary.write_text(json.dumps({'value':progress,'message':stage}))
            temporary.replace(directory/'progress.json')
    def linear(module,value):
        return functional.linear(value.float(),module.weight.float(),
            module.bias.float() if module.bias is not None else None).to(value.dtype)
    def layer_norm(module,value):
        return functional.layer_norm(value.float(),module.normalized_shape,
            module.weight.float() if module.weight is not None else None,
            module.bias.float() if module.bias is not None else None,module.eps).to(value.dtype)
    def stable_ops(network):
        for module in network.modules():
            if isinstance(module,torch.nn.Linear):module.forward=types.MethodType(linear,module)
            elif isinstance(module,torch.nn.Conv2d):module.forward=types.MethodType(_stable_conv_forward,module)
            elif isinstance(module,torch.nn.LayerNorm):module.forward=types.MethodType(layer_norm,module)
    def offload(network,name):
        folder=cache/name;folder.mkdir(parents=True,exist_ok=True)
        disk_offload(network,offload_dir=folder,execution_device=torch.device('cuda:0'),offload_buffers=True)
        cleanup()

    torch.set_num_threads(2)
    torch.backends.cudnn.benchmark=False
    torch.cuda.reset_peak_memory_stats()
    with torch.inference_mode():
        prompt=request.get('effective_prompt','Edit this reference into an elegant professional studio portrait, tailored black blazer, plain light grey background, soft natural lighting. Preserve the same face and hairstyle.')
        log('Preparando el texto para FLUX',3)
        tokenizer=Qwen2TokenizerFast.from_pretrained(path/'tokenizer',local_files_only=True)
        encoder=Qwen3Model.from_pretrained(path/'text_encoder',torch_dtype=torch.bfloat16,
            local_files_only=True,low_cpu_mem_usage=True,attn_implementation='eager')
        stable_ops(encoder)
        log('Preparando memoria para el texto',7)
        offload(encoder,'text')
        log('Interpretando las instrucciones',12)
        chat=tokenizer.apply_chat_template([{'role':'user','content':prompt}],tokenize=False,add_generation_prompt=True,enable_thinking=False)
        tokens=len(tokenizer(chat).input_ids)
        if tokens>512:raise ValueError('Reduce las instrucciones: superan el contexto de FLUX.')
        length=256 if tokens<=256 else 512
        embeds=Flux2KleinPipeline._get_qwen3_prompt_embeds(encoder,tokenizer,prompt,
            device=torch.device('cuda'),dtype=torch.bfloat16,max_sequence_length=length).cpu()
        assert torch.isfinite(embeds).all(),'Non-finite text conditioning'
        del encoder,tokenizer
        cleanup()
        log('Cargando FLUX en memoria reducida',22)
        transformer=Flux2Transformer2DModel.from_pretrained(path/'transformer',torch_dtype=torch.bfloat16,
            local_files_only=True,low_cpu_mem_usage=True)
        stable_ops(transformer)
        offload(transformer,'transformer')
        log('Preparando tu referencia',28)
        vae=AutoencoderKLFlux2.from_pretrained(path/'vae',torch_dtype=torch.float32,
            local_files_only=True,low_cpu_mem_usage=True,device_map={'':0})
        vae.enable_tiling()
        pipe=LowMemoryFluxPipeline(vae=vae,text_encoder=None,tokenizer=None,transformer=transformer,
            scheduler=FlowMatchEulerDiscreteScheduler.from_pretrained(path/'scheduler',local_files_only=True),is_distilled=True)
        original=pipe.prepare_image_latents
        def image_latents(*args,**kwargs):
            values,ids=original(*args,**kwargs)
            return values.to(torch.bfloat16),ids
        pipe.prepare_image_latents=image_latents
        pipe.set_progress_bar_config(disable=True)
        reference=Image.open(directory/'reference.png' if directory else ROOT/'web/assets/demo-reference.jpg').convert('RGB')
        reference.thumbnail((512,512),Image.Resampling.LANCZOS)
        references=[reference]
        character_reference=directory/'character-reference.png' if directory else None
        if character_reference and character_reference.is_file():
            character=Image.open(character_reference).convert('RGB')
            character.thumbnail((256,256),Image.Resampling.LANCZOS)
            references.append(character)
        def callback(pipeline,index,timestep,kwargs):
            assert torch.isfinite(kwargs['latents']).all(),'Non-finite FLUX latents'
            log('FLUX · paso '+str(index+1)+'/4',35+int(50*(index+1)/4))
            return kwargs
        log('Transformando tu fotografía',32)
        size=request.get('output_size',[512,512])
        latents=pipe(prompt_embeds=embeds.to('cuda'),image=references,width=size[0],height=size[1],
            guidance_scale=1.0,num_inference_steps=4,generator=torch.Generator('cpu').manual_seed(request.get('seed',42817)),
            output_type='latent',callback_on_step_end=callback).images.cpu()
        pipe.prepare_image_latents=None
        del original,pipe,transformer,embeds
        cleanup()
        log('Revelando la imagen FLUX',90)
        pixels=vae.decode(latents.to('cuda',dtype=torch.float32),return_dict=False)[0]
        assert torch.isfinite(pixels).all(),'Non-finite FLUX decode'
        pixels=(pixels/2+.5).clamp(0,1).permute(0,2,3,1).cpu().float().numpy()
        del vae
        cleanup()
        log('Comprobando el resultado',95)
        _check_content(pixels)
        image=Image.fromarray((pixels[0]*255).round().astype(np.uint8))
        assert np.asarray(image).std()>5,'Blank FLUX image'
        image.save(directory/'result.png' if directory else output/'flux-klein-low-memory.png')
        report=dict(status='completed',model_id='flux_klein',revision=MODELS['flux_klein']['revision'],
                    output_size=list(image.size),steps=4,seconds=round(time.perf_counter()-start,3),
                    model='FLUX.2 klein 4B · memoria reducida',model_revision=MODELS['flux_klein']['revision'],
                    source_repo=MODELS['flux_klein']['repo_id'],inference_steps=4,identity_strength_applied=False,
                    reference_image_count=len(references),conditioning='multi_image_editing' if len(references)>1 else 'image_editing',
                    gpu=torch.cuda.get_device_name(),peak_vram_allocated_mb=round(torch.cuda.max_memory_allocated()/1024**2,1),
                    mode='experimental BF16 storage, FP32 operators, staged disk offload')
        (directory/'result.json' if directory else output/'flux-klein-low-memory.json').write_text(json.dumps(report,indent=2))
        log('COMPLETE')


if __name__=='__main__':
    if len(sys.argv)>2 and sys.argv[1]=='--worker':
        run(Path(sys.argv[2]))
    else:
        from app.resource_lock import ResourceLock
        with ResourceLock(ROOT/'.runtime/model-resources.lock'):
            run()
