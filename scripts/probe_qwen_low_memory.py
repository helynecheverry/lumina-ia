"""Bounded Qwen Edit + official Lightning LoRA experiment for this GPU.

The LoRA is evaluated per linear layer, without materializing a merged 40GB
checkpoint in RAM. This experiment is not enabled in the UI before validation.
"""
import json
import sys
import time
import types
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def run():
    import numpy as np
    import torch
    import torch.nn.functional as functional
    from PIL import Image
    from safetensors import safe_open
    from accelerate import disk_offload
    from transformers import Qwen2_5_VLModel, AutoProcessor, Qwen2Tokenizer
    from diffusers import QwenImageEditPlusPipeline, QwenImageTransformer2DModel, AutoencoderKLQwenImage, FlowMatchEulerDiscreteScheduler
    import diffusers.pipelines.qwenimage.pipeline_qwenimage_edit_plus as pipeline_module
    from app.influencer_engine import cleanup, _stable_conv_forward, _check_content
    from app.model_registry import WEIGHTS, MODELS
    from app.streamed_lora import linear_with_lora

    start=time.perf_counter()
    def log(text):print(text,round(time.perf_counter()-start,1),flush=True)
    path=WEIGHTS/'qwen_edit'
    adapter=WEIGHTS/'qwen-lightning/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors'
    cache=ROOT/'.runtime/offload'/('qwen-2511-'+MODELS['qwen_edit']['revision'][:12])
    out=ROOT/'artifacts/modern-probes';out.mkdir(parents=True,exist_ok=True)
    class LowMemoryQwen(QwenImageEditPlusPipeline):
        @property
        def _execution_device(self):return torch.device('cuda:0')
        def _encode_vae_image(self,image,generator):
            # The GTX 1650 needs an FP32 image codec; the denoiser keeps BF16 storage.
            return super()._encode_vae_image(image.float(),generator).to(torch.bfloat16)
    def stable_linear(module,value):
        return functional.linear(value.float(),module.weight.float(),module.bias.float() if module.bias is not None else None).to(value.dtype)
    def stable_norm(module,value):
        return functional.layer_norm(value.float(),module.normalized_shape,module.weight.float() if module.weight is not None else None,module.bias.float() if module.bias is not None else None,module.eps).to(value.dtype)
    def stable_ops(network,lora=None):
        matched=set()
        for name,module in network.named_modules():
            if isinstance(module,torch.nn.Linear):
                down=name+'.lora_down.weight';up=name+'.lora_up.weight'
                if lora is not None and down in lora.keys():
                    down_shape=lora.get_slice(down).get_shape();up_shape=lora.get_slice(up).get_shape()
                    assert len(down_shape)==2 and len(up_shape)==2
                    assert down_shape[1]==module.in_features and up_shape[0]==module.out_features,(name,down_shape,up_shape)
                    alpha=name+'.alpha'
                    scale=float(lora.get_tensor(alpha).float())/down_shape[0] if alpha in lora.keys() else 1.0
                    def make_forward(down_key,up_key,strength):
                        def forward(current,value):
                            return linear_with_lora(current,value,lora.get_tensor(down_key),lora.get_tensor(up_key),strength)
                        return forward
                    module.forward=types.MethodType(make_forward(down,up,scale),module)
                    matched.add(name)
                else:module.forward=types.MethodType(stable_linear,module)
            elif isinstance(module,(torch.nn.Conv2d,torch.nn.Conv3d)):
                module.forward=types.MethodType(_stable_conv_forward,module)
            elif isinstance(module,torch.nn.LayerNorm):module.forward=types.MethodType(stable_norm,module)
        if lora is not None:
            expected={key.removesuffix('.lora_down.weight') for key in lora.keys() if key.endswith('.lora_down.weight')}
            assert matched==expected,('Unmapped LoRA layers',expected-matched)
            log('LoRA layers mapped: '+str(len(matched)))
    def offload(network,name):
        folder=cache/name;folder.mkdir(parents=True,exist_ok=True)
        disk_offload(network,offload_dir=folder,execution_device=torch.device('cuda:0'),offload_buffers=True)
        cleanup()

    torch.set_num_threads(2)
    torch.backends.cudnn.benchmark=False
    torch.cuda.reset_peak_memory_stats()
    # Keep the reference VAE workload at the same experimental 512px scale.
    pipeline_module.VAE_IMAGE_SIZE=512*512
    reference=Image.open(ROOT/'web/assets/demo-reference.jpg').convert('RGB')
    reference.thumbnail((512,512),Image.Resampling.LANCZOS)
    prompt='Edit this person into an elegant professional portrait wearing a black tailored blazer, light grey studio background, soft natural light. Preserve the same face and hairstyle.'
    with torch.inference_mode():
        log('Loading multimodal text encoder without language-model head')
        encoder=Qwen2_5_VLModel.from_pretrained(path/'text_encoder',torch_dtype=torch.bfloat16,
            low_cpu_mem_usage=True,local_files_only=True,attn_implementation='eager')
        stable_ops(encoder)
        offload(encoder,'text')
        processor=AutoProcessor.from_pretrained(path/'processor',local_files_only=True)
        tokenizer=Qwen2Tokenizer.from_pretrained(path/'tokenizer',local_files_only=True)
        text_pipe=LowMemoryQwen(scheduler=None,vae=None,text_encoder=encoder,tokenizer=tokenizer,processor=processor,transformer=None)
        log('Encoding reference and instruction')
        embeds,mask=text_pipe.encode_prompt(prompt,image=[reference],device=torch.device('cuda'))
        embeds=embeds.cpu()
        mask=mask.cpu() if mask is not None else None
        assert torch.isfinite(embeds).all(),'Non-finite Qwen text conditioning'
        del text_pipe,encoder,processor,tokenizer
        cleanup()
        log('Loading Qwen denoiser')
        transformer=QwenImageTransformer2DModel.from_pretrained(path/'transformer',torch_dtype=torch.bfloat16,
            local_files_only=True,low_cpu_mem_usage=True)
        with safe_open(adapter,framework='pt',device='cpu') as lora:
            stable_ops(transformer,lora)
            offload(transformer,'transformer')
            log('Preparing image codec')
            vae=AutoencoderKLQwenImage.from_pretrained(path/'vae',torch_dtype=torch.float32,
                low_cpu_mem_usage=True,local_files_only=True,device_map={'':0})
            vae.enable_tiling()
            pipe=LowMemoryQwen(scheduler=FlowMatchEulerDiscreteScheduler.from_pretrained(path/'scheduler',local_files_only=True),
                vae=vae,text_encoder=None,tokenizer=None,processor=None,transformer=transformer)
            pipe.set_progress_bar_config(disable=True)
            def callback(pipeline,index,timestep,kwargs):
                assert torch.isfinite(kwargs['latents']).all(),'Non-finite Qwen latents'
                log('Qwen Lightning step '+str(index+1)+'/4')
                return kwargs
            log('Generating referenced image')
            latents=pipe(prompt_embeds=embeds.to('cuda'),prompt_embeds_mask=mask.to('cuda') if mask is not None else None,image=[reference],
                width=512,height=512,num_inference_steps=4,true_cfg_scale=1.0,guidance_scale=1.0,
                generator=torch.Generator('cpu').manual_seed(42817),output_type='latent',callback_on_step_end=callback).images.cpu()
            log('Decoding')
            latents=pipe._unpack_latents(latents.to('cuda',dtype=torch.float32),512,512,pipe.vae_scale_factor)
            mean=torch.tensor(vae.config.latents_mean,device='cuda').view(1,vae.config.z_dim,1,1,1)
            std=torch.tensor(vae.config.latents_std,device='cuda').view(1,vae.config.z_dim,1,1,1)
            del pipe,transformer,embeds,mask
            cleanup()
            pixels=vae.decode(latents*std+mean,return_dict=False)[0][:,:,0]
            assert torch.isfinite(pixels).all(),'Non-finite Qwen decode'
            pixels=(pixels/2+.5).clamp(0,1).permute(0,2,3,1).cpu().float().numpy()
            del vae
            cleanup()
        _check_content(pixels)
        result=Image.fromarray((pixels[0]*255).round().astype(np.uint8))
        assert np.asarray(result).std()>5,'Blank Qwen image'
        result.save(out/'qwen-lightning-low-memory.png')
        report=dict(status='completed',model_id='qwen_edit',revision=MODELS['qwen_edit']['revision'],
                    adapter='lightx2v/Qwen-Image-Edit-2511-Lightning',adapter_revision='107d238d68b8387e32843d0b4a2e24ceb0d3ad86',
                    output_size=list(result.size),steps=4,seconds=round(time.perf_counter()-start,3),
                    gpu=torch.cuda.get_device_name(),peak_vram_allocated_mb=round(torch.cuda.max_memory_allocated()/1024**2,1),
                    mode='experimental BF16 storage, FP32 operators, staged disk offload, streamed LoRA')
        (out/'qwen-lightning-low-memory.json').write_text(json.dumps(report,indent=2))
        log('COMPLETE')


if __name__=='__main__':
    from app.resource_lock import ResourceLock
    with ResourceLock(ROOT/'.runtime/model-resources.lock'):run()
