"""One dispatch contract, compatible pipelines, one shared GPU lock."""
import json
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from app import engine
from app.influencer_engine import generate as generate_light, GenerationCancelled, cleanup
from app.model_registry import ROOT, MODELS, model_status, validate_selection, DEFAULT_MODEL
from app.prompting import compile_studio_prompt


def generate(raw, model_id=DEFAULT_MODEL, framing='square', **options):
    size = validate_selection(model_id, framing)
    if options.get('target_age') is not None:
        from app.youth import youth_recipe
        youth_recipe(options['target_age'], model_id, framing, size)
    if model_id == DEFAULT_MODEL:
        output, metadata = generate_light(raw, output_size=size, **options)
        return output, dict(metadata, model_id=model_id, framing=framing)
    status = model_status(model_id)
    if not status['ready']:
        raise ValueError(status['reason'])
    if model_id == 'portrait_sdxl':
        from app.sdxl_engine import generate as generate_xl
        return generate_xl(raw, framing=framing, **options)
    return generate_modern(raw, model_id, framing, size, **options)


def generate_modern(raw, model_id, framing, size, preset='editorial', prompt='', seed=42,
                    identity_strength=.6, steps=32, progress=lambda *args: None,
                    cancelled=lambda: False, character_type='natural', appearance=None, inspiration_id='', target_age=None):
    start = time.perf_counter()
    process = None
    unit = None
    with engine._lock:
        engine.unload_engine()
        cleanup()
        recipe = compile_studio_prompt(preset, prompt, character_type=character_type, model_id=model_id, framing=framing, appearance=appearance, inspiration_id=inspiration_id, target_age=target_age)
        instruction = recipe['effective_prompt']
        cleanup()  # Return the translator's CPU allocations before launching another runtime.
        with tempfile.TemporaryDirectory(prefix='lumina-', dir=ROOT/'.runtime') as task:
            directory = Path(task)
            (directory/'reference.png').write_bytes(engine.encode(engine.decode(raw)))
            (directory/'request.json').write_text(json.dumps(dict(model_id=model_id, framing=framing,
                output_size=size, seed=seed, steps=steps, effective_prompt=instruction,
                negative_prompt=recipe['negative_prompt'])))
            try:
                with (directory/'worker.log').open('w+') as log:
                    if model_id=='flux_klein' and model_status(model_id).get('low_memory'):
                        unit='lumina-flux-'+uuid.uuid4().hex
                        command=['systemd-run','--user','--scope','--quiet','--unit='+unit,
                            '-p','MemoryMax=1800M','-p','MemorySwapMax=0','timeout','600',
                            str(ROOT/'.runtime/modern/bin/python'),str(ROOT/'scripts/probe_flux_low_memory.py'),
                            '--worker',str(directory)]
                    else:
                        command=[str(ROOT/'.runtime/modern/bin/python'),'-m','app.modern_worker',str(directory)]
                    process = subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
                    previous = None
                    while process.poll() is None:
                        if cancelled():
                            raise GenerationCancelled()
                        if time.perf_counter()-start > 3600:
                            raise ValueError('El editor excedió una hora de ejecución; reduce la carga o usa otro motor.')
                        state = directory/'progress.json'
                        if state.is_file():
                            value = json.loads(state.read_text())
                            if value != previous:
                                progress(value['value'], value['message'])
                                previous = value
                        time.sleep(.25)
                    if process.returncode:
                        log.seek(0)
                        import logging
                        logging.error('Modern worker failed: %s', log.read()[-12000:])
                        raise ValueError('El editor no pudo completar la imagen. Revisa recursos, pesos y registros del servidor.')
                if cancelled():
                    raise GenerationCancelled()
                output = (directory/'result.png').read_bytes()
                metadata = json.loads((directory/'result.json').read_text())
                metadata.pop('steps',None)  # Keep requested steps; inference_steps records distilled steps.
                return output, {**recipe, **metadata, 'effective_edit_instruction':instruction,
                    'model_id':model_id, 'framing':framing, 'device':'cuda', 'seconds':round(time.perf_counter()-start,3)}
            finally:
                if unit and process is not None and process.poll() is None:
                    subprocess.run(['systemctl','--user','stop',unit+'.scope'],
                        timeout=10,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
                if process is not None and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                cleanup()
