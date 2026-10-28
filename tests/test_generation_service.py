"""Queue contracts against an isolated MongoDB DB; diffusion is stubbed here.
The separate scripts/test_influencer_api.py executes the actual GPU model.
"""
import io
import sys
import threading
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image
from skimage import data
from fastapi import HTTPException
from pymongo import MongoClient
from app.generation_service import GenerationService

class GenerationServiceTest(unittest.TestCase):
    def setUp(self):
        self.client = MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=2000)
        self.db_name = 'test_lumina_' + uuid.uuid4().hex
        self.db = self.client[self.db_name]
        self.service = GenerationService(self.db)
        self.db.generations.create_index('request_key', unique=True)
        buf = io.BytesIO(); Image.fromarray(data.astronaut()).save(buf, 'PNG')
        self.raw = buf.getvalue()
        self.ready = patch('app.generation_service.readiness', return_value={'ready': True, 'model': 'test-only'})
        self.ready.start()

    def tearDown(self):
        self.service.stop()
        self.ready.stop()
        self.client.drop_database(self.db_name)
        self.client.close()

    def submit(self, key=None, **kwargs):
        values = dict(raw=self.raw, filename='portrait.png', preset='cinema', prompt='', seed=42,
                      identity_strength=.8, steps=20, request_key=key or str(uuid.uuid4()))
        values.update(kwargs)
        return self.service.submit(**values)

    def test_youth_age_persists_reaches_worker_and_changes_fingerprint(self):
        with patch('app.generation_service.model_status',return_value={'ready':True,'model':'test-editor'}), patch('app.generation_service.validate_selection',return_value=[512,512]):
            key=str(uuid.uuid4())
            job=self.submit(key,model_id='flux_klein',preset='editorial',target_age=14)
            self.assertEqual(job['target_age'],14)
            self.assertEqual(job['creation_mode'],'youth')
            with self.assertRaises(HTTPException) as error:
                self.submit(key,model_id='flux_klein',preset='editorial',target_age=10)
            self.assertEqual(error.exception.status_code,409)
            self.db.generations.update_one({}, {'$set':{'status':'processing'}})
            with patch('app.generation_service.generate',return_value=(self.raw,{})) as inference:
                self.service.process(self.service.get(job['id']))
            self.assertEqual(inference.call_args.kwargs['target_age'],14)

    def test_youth_rejects_invalid_age_or_conflicting_options_before_storage(self):
        for options in ({'target_age':18}, {'target_age':14,'inspiration_id':'pokemon:pikachu'}, {'target_age':14,'prompt':'costume'}, {'target_age':14,'model_id':'portrait_sd15'}):
            args=dict(model_id='flux_klein',preset='editorial');args.update(options)
            with patch('app.generation_service.validate_selection',return_value=[512,512]), self.assertRaises(HTTPException) as error:
                self.submit(**args)
            self.assertEqual(error.exception.status_code,400)
        self.assertEqual(self.db.fs.files.count_documents({}),0)

    def test_idempotent_submit_and_conflict(self):
        key = str(uuid.uuid4())
        first = self.submit(key)
        self.assertEqual(first['id'], self.submit(key)['id'])
        self.assertEqual(self.db.fs.files.count_documents({}), 1)
        with self.assertRaises(HTTPException) as error:
            self.submit(key, seed=99)
        self.assertEqual(error.exception.status_code, 409)

    def test_discovery_target_persists_reaches_worker_and_changes_fingerprint(self):
        key=str(uuid.uuid4())
        job=self.submit(key,inspiration_id='pokemon:pikachu')
        self.assertEqual(job['inspiration_id'],'pokemon:pikachu')
        self.assertEqual(job['inspiration_name'],'Pikachu')
        with self.assertRaises(HTTPException) as error:self.submit(key,inspiration_id='pokemon:eevee')
        self.assertEqual(error.exception.status_code,409)
        self.db.generations.update_one({}, {'$set': {'status':'processing'}})
        with patch('app.generation_service.generate',return_value=(self.raw,{})) as inference:
            self.service.process(self.service.get(job['id']))
        self.assertEqual(inference.call_args.kwargs['inspiration_id'],'pokemon:pikachu')

    def test_unknown_discovery_target_does_not_store_photo(self):
        with self.assertRaises(HTTPException) as error:self.submit(inspiration_id='pokemon:fake')
        self.assertEqual(error.exception.status_code,400)
        self.assertEqual(self.db.fs.files.count_documents({}),0)

    def test_character_type_persists_and_reaches_engine(self):
        job=self.submit(character_type='bold')
        self.assertEqual(job['character_type'],'bold')
        self.db.generations.update_one({}, {'$set': {'status':'processing'}})
        with patch('app.generation_service.generate',return_value=(self.raw,{'character_type':'bold'})) as inference:
            self.service.process(self.service.get(job['id']))
        self.assertEqual(inference.call_args.kwargs['character_type'],'bold')
        self.assertEqual(self.service.public(self.service.get(job['id']))['character_type'],'bold')

    def test_character_type_is_part_of_idempotency(self):
        key=str(uuid.uuid4())
        self.submit(key,character_type='natural')
        with self.assertRaises(HTTPException) as error:
            self.submit(key,character_type='bold')
        self.assertEqual(error.exception.status_code,409)
        self.assertEqual(self.db.fs.files.count_documents({}),1)

    def test_motor_and_framing_persist_reach_worker_and_conflict(self):
        with patch('app.generation_service.model_status',return_value={'ready':True,'label':'XL'}):
            key=str(uuid.uuid4())
            job=self.submit(key,model_id='portrait_sdxl',framing='portrait')
            self.assertEqual(job['model_id'],'portrait_sdxl')
            self.assertEqual(job['framing'],'portrait')
            with self.assertRaises(HTTPException) as error:
                self.submit(key,model_id='portrait_sdxl',framing='square')
            self.assertEqual(error.exception.status_code,409)
            with patch('app.generation_service.generate',return_value=(self.raw,{'output_size':[768,1024]})) as inference:
                self.db.generations.update_one({}, {'$set': {'status':'processing'}})
                self.service.process(self.service.get(job['id']))
            self.assertEqual(inference.call_args.kwargs['model_id'],'portrait_sdxl')
            self.assertEqual(inference.call_args.kwargs['framing'],'portrait')

    def test_unavailable_model_cannot_enqueue_or_store_image(self):
        with patch('app.generation_service.model_status',return_value={'ready':False,'reason':'Insufficient memory'}):
            with self.assertRaises(HTTPException) as error:
                self.submit(model_id='qwen_edit')
            self.assertEqual(error.exception.status_code,503)
            self.assertEqual(self.db.generations.count_documents({}),0)
            self.assertEqual(self.db.fs.files.count_documents({}),0)

    def test_unknown_model_and_framing_are_rejected(self):
        for values in [{'model_id':'unknown'},{'framing':'arbitrary'}]:
            with self.assertRaises(HTTPException) as error:
                self.submit(**values)
            self.assertEqual(error.exception.status_code,400)
        self.assertEqual(self.db.fs.files.count_documents({}),0)

    def test_appearance_reaches_worker_and_survives_reload(self):
        appearance={'outfit':'red_jacket','lighting':'dramatic'}
        key=str(uuid.uuid4())
        job=self.submit(key,appearance=appearance,character_type='cyborg')
        self.assertEqual(job['appearance'],appearance)
        with self.assertRaises(HTTPException) as error:
            self.submit(key,appearance={'outfit':'blue_jacket'},character_type='cyborg')
        self.assertEqual(error.exception.status_code,409)
        self.db.generations.update_one({}, {'$set':{'status':'processing'}})
        with patch('app.generation_service.generate',return_value=(self.raw,{})) as inference:
            self.service.process(self.service.get(job['id']))
        self.assertEqual(inference.call_args.kwargs['appearance'],appearance)
        self.assertEqual(inference.call_args.kwargs['character_type'],'cyborg')

    def test_four_distilled_steps_do_not_enable_invalid_classic_steps(self):
        with patch('app.generation_service.model_status',return_value={'ready':True,'label':'FLUX'}):
            self.assertEqual(self.submit(model_id='flux_klein',steps=4)['steps'],4)
        with self.assertRaises(HTTPException) as error:self.submit(steps=4)
        self.assertEqual(error.exception.status_code,400)

    def test_invalid_character_type_is_not_stored(self):
        with self.assertRaises(HTTPException) as error:
            self.submit(character_type='fake')
        self.assertEqual(error.exception.status_code,400)
        self.assertEqual(self.db.fs.files.count_documents({}),0)

    def test_cancel_queued_keeps_reference(self):
        job = self.submit()
        cancelled = self.service.cancel(job['id'])
        self.assertEqual(cancelled['status'], 'cancelled')
        self.assertEqual(self.db.fs.files.count_documents({}), 1)
        self.assertFalse(cancelled['has_image'])

    def test_queue_capacity(self):
        for _ in range(4):
            self.submit()
        with self.assertRaises(HTTPException) as error:
            self.submit()
        self.assertEqual(error.exception.status_code, 429)
        self.assertEqual(self.db.fs.files.count_documents({}), 4)

    def test_no_face_does_not_store_file(self):
        buf = io.BytesIO(); Image.new('RGB', (128,128)).save(buf, 'PNG')
        with self.assertRaises(HTTPException) as error:
            self.submit(raw=buf.getvalue())
        self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(self.db.fs.files.count_documents({}), 0)

    def test_cancel_during_inference_has_no_output(self):
        job = self.submit()
        self.db.generations.update_one({}, {'$set': {'status': 'processing'}})
        from app.influencer_engine import GenerationCancelled
        def fake_generate(*args, **kwargs):
            self.service.cancel(job['id'])
            self.assertTrue(kwargs['cancelled']())
            raise GenerationCancelled()
        with patch('app.generation_service.generate', side_effect=fake_generate):
            self.service.process(self.service.get(job['id']))
        self.assertEqual(self.service.get(job['id'])['status'], 'cancelled')
        self.assertEqual(self.db.fs.files.count_documents({}), 1)

    def test_completed_output_is_stored(self):
        job = self.submit()
        self.db.generations.update_one({}, {'$set': {'status': 'processing'}})
        with patch('app.generation_service.generate', return_value=(self.raw, {'seconds': 1., 'output_size': [512,512]})):
            self.service.process(self.service.get(job['id']))
        self.assertEqual(self.service.get(job['id'])['status'], 'completed')
        self.assertEqual(self.db.fs.files.count_documents({}), 2)
        exposed = self.service.public(self.service.get(job['id']))
        self.assertNotIn('input_gridfs_id', exposed)
        self.assertNotIn('request_key', exposed)

if __name__ == '__main__':
    unittest.main()
