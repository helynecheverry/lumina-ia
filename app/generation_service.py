"""Durable single-GPU queue. Images never leave this machine."""
import datetime
import hashlib
import json
import logging
import threading
import uuid

from bson import ObjectId
from fastapi import HTTPException
from gridfs import GridFS
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.engine import encode, decode
from app.character_types import CHARACTER_TYPES
from app.influencer_engine import PRESETS, readiness, face_crop, GenerationCancelled
from app.studio_engine import generate
from app.model_registry import DEFAULT_MODEL, model_status, validate_selection
from app.appearance import validate_appearance

ACTIVE = ('queued', 'processing')
TERMINAL = ('completed', 'failed', 'cancelled', 'interrupted')


def now():
    return datetime.datetime.now(datetime.timezone.utc)


class GenerationService:
    def __init__(self, db):
        self.db = db
        self.fs = GridFS(db)
        self.stop_event = threading.Event()
        self.thread = None
        self.submit_lock = threading.Lock()

    def start(self):
        self.db.generations.create_index('request_key', unique=True)
        self.db.generations.create_index([('created_at', -1)])
        # A process crash cannot safely resume the diffusion latents.
        self.db.generations.update_many({'status': 'processing'}, {'$set': {
            'status': 'interrupted', 'message': 'El servidor se reinició. Puedes crear otra variación.', 'updated_at': now()}})
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.run, name='local-portrait-worker', daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)

    def submit(self, raw, filename, preset, prompt, seed, identity_strength, steps, request_key, character_type='natural',
               model_id=DEFAULT_MODEL, framing='square', appearance=None, inspiration_id='', target_age=None):
        try:
            from app.youth import validate_target_age, youth_recipe
            validate_target_age(target_age)
            if target_age is not None:
                youth_recipe(target_age, model_id, framing, validate_selection(model_id, framing))
                if inspiration_id or prompt.strip() or appearance or character_type != 'natural' or preset != 'editorial':
                    raise ValueError('La versión joven utiliza un retrato natural, sin personajes ni instrucciones adicionales.')
            validate_selection(model_id, framing)
            appearance = validate_appearance(appearance)
            if inspiration_id:
                from app.discovery_catalog import get_inspiration
                get_inspiration(inspiration_id)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        selected = readiness() if model_id == DEFAULT_MODEL else model_status(model_id)
        if not selected['ready']:
            raise HTTPException(503, selected.get('reason') or 'El motor local todavía no está listo; faltan pesos o GPU CUDA.')
        if character_type not in CHARACTER_TYPES:
            raise HTTPException(400, 'Tipo de personaje inválido')
        valid_steps = 12 <= steps <= 40 or (model_id=='flux_klein' and steps==4)
        if preset not in PRESETS or not 0 <= seed <= 2147483647 or not .3 <= identity_strength <= 1.2 or not valid_steps:
            raise HTTPException(400, 'Estilo o parámetros fuera de rango')
        if len(prompt) > 500:
            raise HTTPException(400, 'La descripción admite hasta 500 caracteres')
        try:
            request_key = str(uuid.UUID(request_key))
        except ValueError as exc:
            raise HTTPException(400, 'Identificador de solicitud inválido') from exc
        options = {'preset': preset, 'prompt': prompt, 'seed': seed, 'identity_strength': identity_strength, 'steps': steps,
                   'character_type': character_type, 'model_id': model_id, 'framing': framing, 'appearance':appearance}
        if target_age is not None: options.update(target_age=target_age, creation_mode='youth', character_label=f'Tu versión a los {target_age} años')
        if inspiration_id: options['inspiration_id']=inspiration_id
        fingerprint = hashlib.sha256(raw + json.dumps(options, sort_keys=True).encode()).hexdigest()
        with self.submit_lock:
            previous = self.db.generations.find_one({'request_key': request_key})
            if previous:
                if previous['fingerprint'] != fingerprint:
                    raise HTTPException(409, 'La solicitud ya existe con otra imagen o parámetros')
                return self.public(previous)
            if self.db.generations.count_documents({'status': {'$in': ACTIVE}}) >= 4:
                raise HTTPException(429, 'La cola está llena. Espera a que termine una creación.')
            try:
                _, box = face_crop(raw)
                normalized = encode(decode(raw))
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
            fid = self.fs.put(normalized, filename='reference.png', content_type='image/png')
            try:
                doc = {'_id': ObjectId(), 'created_at': now(), 'updated_at': now(), 'filename': filename,
                       'status': 'queued', 'progress': 0, 'message': 'En cola', 'request_key': request_key,
                       'fingerprint': fingerprint, 'input_gridfs_id': fid, 'face_box': box,
                       'model': selected.get('model', selected.get('label')), 'provider': 'local', 'cancel_requested': False,
                       **options}
                if inspiration_id:
                    from app.discovery_catalog import CATEGORIES
                    target=get_inspiration(inspiration_id)
                    doc.update(inspiration_name=target['name'],inspiration_category=target['category'],
                               character_label=target['name']+' · '+CATEGORIES[target['category']]['label'])
                self.db.generations.insert_one(doc)
            except Exception:
                self.fs.delete(fid)
                raise
        return self.public(doc)

    @staticmethod
    def public(doc):
        result = {key: value for key, value in doc.items() if key not in (
            '_id', 'input_gridfs_id', 'gridfs_id', 'fingerprint', 'request_key', 'cancel_requested')}
        result['id'] = str(doc['_id'])
        for key in ('created_at', 'updated_at'):
            if key in result:
                result[key] = result[key].isoformat()
        result['has_image'] = 'gridfs_id' in doc
        return result

    def get(self, job_id):
        if not ObjectId.is_valid(job_id):
            raise HTTPException(400, 'ID inválido')
        doc = self.db.generations.find_one({'_id': ObjectId(job_id)})
        if not doc:
            raise HTTPException(404, 'Creación no encontrada')
        return doc

    def cancel(self, job_id):
        doc = self.get(job_id)
        self.db.generations.update_one({'_id': doc['_id'], 'status': 'queued'}, {'$set': {
            'status': 'cancelled', 'message': 'Cancelada', 'cancel_requested': True, 'updated_at': now()}})
        self.db.generations.update_one({'_id': doc['_id'], 'status': 'processing'}, {'$set': {
            'cancel_requested': True, 'message': 'Cancelando al terminar el paso actual', 'updated_at': now()}})
        return self.public(self.get(job_id))

    def run(self):
        while not self.stop_event.is_set():
            try:
                doc = self.db.generations.find_one_and_update({'status': 'queued'}, {'$set': {
                    'status': 'processing', 'message': 'Preparando tu creación', 'updated_at': now()}},
                    sort=[('created_at', 1)], return_document=ReturnDocument.AFTER)
                if doc:
                    self.process(doc)
                    continue
            except Exception:
                logging.exception('Fallo temporal en la cola de retratos')
            self.stop_event.wait(1)

    def process(self, doc):
        fid = None
        job_id = doc['_id']
        def cancelled():
            current = self.db.generations.find_one({'_id': job_id}, {'cancel_requested': 1})
            return self.stop_event.is_set() or not current or current.get('cancel_requested', False)
        def progress(value, message):
            self.db.generations.update_one({'_id': job_id, 'status': 'processing'}, {'$set': {
                'progress': value, 'message': message, 'updated_at': now()}})
        try:
            raw = self.fs.get(doc['input_gridfs_id']).read()
            discovery_options = {'inspiration_id':doc['inspiration_id']} if doc.get('inspiration_id') else {}
            if doc.get('target_age') is not None: discovery_options['target_age']=doc['target_age']
            result, metadata = generate(raw, preset=doc['preset'], prompt=doc['prompt'], seed=doc['seed'],
                identity_strength=doc['identity_strength'], steps=doc['steps'], progress=progress, cancelled=cancelled,
                character_type=doc.get('character_type', 'natural'), model_id=doc.get('model_id', DEFAULT_MODEL),
                framing=doc.get('framing', 'square'), appearance=doc.get('appearance', {}), **discovery_options)
            if cancelled():
                raise GenerationCancelled()
            fid = self.fs.put(result, filename='portrait.png', content_type='image/png')
            # A cancellation arriving during GridFS write must also win.
            changed = self.db.generations.update_one({'_id': job_id, 'status': 'processing', 'cancel_requested': False}, {'$set': {
                'status': 'completed', 'progress': 100, 'message': 'Tu imagen está lista',
                'gridfs_id': fid, 'updated_at': now(), **metadata}})
            if not changed.modified_count:
                self.fs.delete(fid)
                fid = None
                raise GenerationCancelled()
        except GenerationCancelled:
            self.db.generations.update_one({'_id': job_id}, {'$set': {'status': 'cancelled',
                'message': 'Creación cancelada', 'updated_at': now()}})
        except Exception as exc:
            logging.exception('No se pudo generar el retrato %s', job_id)
            if fid is not None:
                self.fs.delete(fid)
            message = str(exc) if isinstance(exc, ValueError) else 'No se pudo generar. Revisa la memoria disponible y los registros del motor.'
            self.db.generations.update_one({'_id': job_id}, {'$set': {'status': 'failed',
                'message': message, 'updated_at': now()}})
