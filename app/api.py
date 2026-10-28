"""Local image studio API backed by MongoDB and GridFS."""
import base64
import json
import datetime
import logging
import os
import time
from contextlib import asynccontextmanager

from bson import ObjectId
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from gridfs import GridFS
from gridfs.errors import NoFile
from pymongo import MongoClient, DESCENDING
from pymongo.errors import PyMongoError
from app.engine import restore, edit, model_path, torch, FILTERS, _lock
from app.generation_service import GenerationService
from app.influencer_engine import readiness, PRESETS
from app.prompting import compile_studio_prompt
from app.character_types import CHARACTER_TYPES
from app.model_registry import catalog, DEFAULT_MODEL, validate_selection
from app.appearance import public_controls
from pydantic import BaseModel, Field

client = MongoClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017'), serverSelectionTimeoutMS=2000)
db = client[os.getenv('MONGO_DB', 'face_restoration')]
MAX = int(os.getenv('MAX_UPLOAD_MB', '10')) * 1024 * 1024
generations = GenerationService(db)


@asynccontextmanager
async def lifespan(app):
    try:
        db.jobs.create_index([('created_at', DESCENDING)])
        db.edits.create_index([('created_at', DESCENDING)])
        generations.start()
    except PyMongoError:
        logging.warning('MongoDB no disponible durante el inicio')
    yield
    generations.stop()
    client.close()


app = FastAPI(title='Lúmina · Image Studio', version='3.0', lifespan=lifespan)


def require_db():
    try:
        client.admin.command('ping')
    except PyMongoError as exc:
        raise HTTPException(503, 'MongoDB no disponible') from exc


def save(raw, collection, metadata):
    fs = GridFS(db)
    fid = None
    try:
        fid = fs.put(raw, filename='result.png', content_type='image/png')
        doc = dict(metadata, created_at=datetime.datetime.now(datetime.timezone.utc), gridfs_id=fid, status='completed')
        return str(db[collection].insert_one(doc).inserted_id)
    except PyMongoError as exc:
        if fid is not None:
            try:
                fs.delete(fid)
            except PyMongoError:
                logging.exception('No se pudo limpiar el archivo GridFS')
        raise HTTPException(503, 'No se pudo guardar en MongoDB') from exc


async def read_upload(file):
    if file.content_type not in ('image/jpeg', 'image/png', 'image/webp'):
        raise HTTPException(415, 'Solo imágenes JPEG, PNG o WebP')
    raw = await file.read(MAX + 1)
    if len(raw) > MAX:
        raise HTTPException(413, 'Archivo demasiado grande')
    return raw


@app.get('/health')
def health():
    try:
        require_db()
        mongo = 'ok'
    except HTTPException:
        mongo = 'disconnected'
    return {'api': 'ok', 'mongodb': mongo, 'model': 'available' if model_path().is_file() else 'missing',
            'device': 'cuda' if torch.cuda.is_available() else 'cpu', 'max_upload_mb': MAX // 1024 // 1024}


@app.post('/restore')
async def reconstruct(file: UploadFile = File(...), scale: float = Form(4)):
    if not 1 <= scale <= 4:
        raise HTTPException(400, 'Escala 1 a 4')
    raw = await read_upload(file)
    await run_in_threadpool(require_db)
    try:
        start = time.perf_counter()
        result, device, old, new = await run_in_threadpool(restore, raw, scale)
        elapsed = round(time.perf_counter() - start, 3)
        job_id = await run_in_threadpool(save, result, 'jobs', {'filename': file.filename, 'device': device,
            'input_size': old, 'output_size': new, 'scale': scale, 'seconds': elapsed})
        return {'id': job_id, 'device': device, 'seconds': elapsed, 'input_size': old, 'output_size': new,
                'image_base64': base64.b64encode(result).decode('ascii')}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        logging.exception('Error de inferencia')
        raise HTTPException(503, 'No fue posible ejecutar el modelo; revise pesos, memoria y registros') from exc


@app.post('/edit')
async def editing(file: UploadFile = File(...), brightness: int = Form(0), contrast: float = Form(1),
                  filter_name: str = Form('none'), save_result: bool = Form(True)):
    if not (-100 <= brightness <= 100 and .2 <= contrast <= 3) or filter_name not in FILTERS:
        raise HTTPException(400, 'Parámetros fuera de rango o filtro inválido')
    raw = await read_upload(file)
    if save_result:
        await run_in_threadpool(require_db)
    try:
        result = await run_in_threadpool(edit, raw, brightness, contrast, filter_name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    edit_id = None
    if save_result:
        edit_id = await run_in_threadpool(save, result, 'edits', {'filename': file.filename,
            'brightness': brightness, 'contrast': contrast, 'filter': filter_name})
    return {'id': edit_id, 'saved': edit_id is not None, 'image_base64': base64.b64encode(result).decode('ascii')}


@app.get('/history')
def history(limit: int = Query(50, ge=1, le=200), kind: str = Query('jobs', pattern='^(jobs|edits|generations)$')):
    require_db()
    try:
        rows = []
        for doc in db[kind].find().sort('created_at', -1).limit(limit):
            doc['id'] = str(doc.pop('_id'))
            doc['has_image'] = 'gridfs_id' in doc
            for private_key in ('gridfs_id', 'input_gridfs_id', 'request_key', 'fingerprint', 'cancel_requested'):
                doc.pop(private_key, None)
            if 'updated_at' in doc:
                doc['updated_at'] = doc['updated_at'].isoformat()
            doc['created_at'] = doc['created_at'].isoformat()
            rows.append(doc)
        return rows
    except PyMongoError as exc:
        raise HTTPException(503, 'No se pudo consultar MongoDB') from exc


@app.get('/image/{id}')
def image(id: str, kind: str = Query('jobs', pattern='^(jobs|edits|generations)$')):
    if not ObjectId.is_valid(id):
        raise HTTPException(400, 'ID inválido')
    require_db()
    try:
        doc = db[kind].find_one({'_id': ObjectId(id)})
        if not doc:
            raise HTTPException(404, 'No encontrado')
        if 'gridfs_id' not in doc:
            raise HTTPException(409, 'La imagen todavía no está lista')
        return Response(GridFS(db).get(doc['gridfs_id']).read(), media_type='image/png')
    except NoFile as exc:
        raise HTTPException(404, 'Imagen no encontrada') from exc
    except PyMongoError as exc:
        raise HTTPException(503, 'No se pudo leer MongoDB') from exc


@app.get('/influencer/config')
def influencer_config():
    from pathlib import Path
    assets = Path(__file__).resolve().parent / 'assets/portraits'
    def preview(value, path):
        available = path.is_file()
        url = value['preview'].split('?')[0]
        return dict(value, preview_available=available,
                    preview=f'{url}?v={path.stat().st_mtime_ns:x}' if available else url,
                    preview_kind='concept_illustration')
    presets = {key: preview(value, assets/(key+'.png')) for key,value in PRESETS.items()}
    operational = catalog()
    characters = {key: preview(value, assets.parent/'characters'/(key+'.png'))
                  for key,value in CHARACTER_TYPES.items()}
    return dict(readiness(), ready=any(model['ready'] for model in operational['models'].values()),
                presets=presets, character_types=characters, appearance_controls=public_controls(), max_queue=4, **operational)


@app.get('/influencer/models')
def studio_models():
    return catalog()


@app.post('/influencer/generations', status_code=202)
async def create_portrait(file: UploadFile = File(...), preset: str = Form('editorial'),
                          prompt: str = Form(''), seed: int = Form(42),
                          identity_strength: float = Form(.6), steps: int = Form(32),
                          request_key: str = Form(...), character_type: str = Form('natural'),
                          model_id: str = Form(DEFAULT_MODEL), framing: str = Form('square'),
                          appearance: str = Form('{}'), inspiration_id: str = Form(''), target_age: int | None = Form(None)):
    try:
        if len(appearance) > 2000:
            raise ValueError()
        visual_options = json.loads(appearance)
    except ValueError as exc:
        raise HTTPException(400, 'Opciones visuales inválidas') from exc
    raw = await read_upload(file)
    await run_in_threadpool(require_db)
    return await run_in_threadpool(generations.submit, raw, file.filename, preset, prompt, seed,
                                   identity_strength, steps, request_key, character_type, model_id, framing, visual_options, inspiration_id, target_age)


@app.get('/influencer/generations/{job_id}')
def get_portrait(job_id: str):
    require_db()
    return generations.public(generations.get(job_id))


@app.post('/influencer/generations/{job_id}/cancel')
def cancel_portrait(job_id: str):
    require_db()
    return generations.cancel(job_id)


@app.get('/influencer/generations/{job_id}/reference')
def get_portrait_reference(job_id: str):
    require_db()
    doc = generations.get(job_id)
    try:
        return Response(GridFS(db).get(doc['input_gridfs_id']).read(), media_type='image/png')
    except NoFile as exc:
        raise HTTPException(404, 'Referencia no encontrada') from exc


class PromptPreview(BaseModel):
    preset: str
    prompt: str = Field(default='', max_length=500)
    character_type: str = 'natural'
    model_id: str = DEFAULT_MODEL
    framing: str = 'square'
    appearance: dict = Field(default_factory=dict)
    inspiration_id: str = ''
    target_age: int | None = None


def compile_preview_safely(payload):
    # Marian has a material RAM footprint. Never load it beside diffusion or
    # another preview on small machines, even if HTTP requests are concurrent.
    if not _lock.acquire(blocking=False):
        raise HTTPException(409, 'Hay una creación o mejora en curso. Espera a que termine para interpretar instrucciones nuevas.')
    try:
        return compile_studio_prompt(payload.preset, payload.prompt, character_type=payload.character_type,
                                     model_id=payload.model_id, framing=payload.framing, appearance=payload.appearance, inspiration_id=payload.inspiration_id, target_age=payload.target_age)
    finally:
        from app.influencer_engine import cleanup
        try:
            cleanup()
        finally:
            _lock.release()


@app.post('/influencer/prompt-preview')
async def prompt_preview(payload: PromptPreview):
    try:
        validate_selection(payload.model_id, payload.framing)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if payload.character_type not in CHARACTER_TYPES:
        raise HTTPException(400, 'Tipo de personaje inválido')
    if payload.preset not in PRESETS:
        raise HTTPException(400, 'Estilo inválido')
    try:
        return await run_in_threadpool(compile_preview_safely, payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get('/influencer/discovery')
def discovery_catalog():
    from app.discovery_catalog import public_catalog,VERSION
    from app.discovery_matcher import readiness
    return dict(version=VERSION,categories=public_catalog(),matcher_ready=readiness(),method='local_clip_face_affinity_v2')


@app.post('/influencer/discovery/match')
async def discover_character(file: UploadFile=File(...),category: str=Form('pokemon')):
    from app.discovery_matcher import match
    raw=await read_upload(file)
    try:
        return await run_in_threadpool(match,raw,category)
    except ValueError as exc:
        raise HTTPException(400,str(exc)) from exc
