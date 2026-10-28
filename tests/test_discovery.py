"""Discovery contracts: explicit targets, ranking and shared-memory coordination."""
import unittest
from unittest.mock import patch
import numpy as np
from fastapi import HTTPException
from app.discovery_catalog import ENTRIES, public_catalog, get_inspiration
from app.discovery_matcher import rank, match
from app.prompting import compile_prompt, compile_studio_prompt

class DiscoveryTest(unittest.TestCase):
    def test_catalog_references_exist_and_ids_are_unique(self):
        catalog=public_catalog()
        self.assertEqual({key:len(group['items']) for key,group in catalog.items()},dict(pokemon=16,digimon=12,zodiac=12))
        self.assertEqual(len(ENTRIES),40)
        for category,group in catalog.items():
            for item in group['items']:
                self.assertEqual(item['category'],category)
                if category!='zodiac':self.assertIsNotNone(item['image'])
        with self.assertRaises(ValueError):get_inspiration('pokemon:unknown')

    def test_explicit_target_does_not_inherit_selected_fox(self):
        recipe=compile_prompt('three_d','Pikachu',translated='Pikachu',character_type='fox',inspiration_id='pokemon:pikachu')
        self.assertEqual(recipe['inspiration_id'],'pokemon:pikachu')
        self.assertIn('round red cheek markings',recipe['effective_prompt'])
        self.assertNotIn('orange and cream fur',recipe['effective_prompt'])
        self.assertEqual(recipe['transformation_intensity'],'strong')

    def test_modern_recipe_preserves_target_and_personal_cues(self):
        with patch('app.prompting.translate_prompt',return_value=('Agumon','en')),patch('app.model_registry.validate_selection',return_value=[512,512]):
            recipe=compile_studio_prompt('three_d','Agumon',model_id='flux_klein',inspiration_id='digimon:agumon')
        self.assertEqual(recipe['inspiration_category'],'digimon')
        self.assertIn('golden yellow dinosaur skin',recipe['effective_prompt'])
        self.assertIn('reference person',recipe['effective_prompt'])

    def test_generated_discovery_description_uses_visual_traits_without_cartoon_name_bias(self):
        text='Conviérteme en una criatura humanoide inspirada en Pikachu, conservando algunos rasgos de mi foto.'
        with patch('app.prompting.translate_prompt',return_value=('Make me a humanoid creature inspired by Pikachu','en')),patch('app.model_registry.validate_selection',return_value=[512,512]):
            recipe=compile_studio_prompt('cinema',text,model_id='flux_klein',inspiration_id='pokemon:pikachu')
        self.assertNotIn('Pikachu',recipe['effective_prompt'])
        self.assertIn('round red cheek markings',recipe['effective_prompt'])
        self.assertIn('underlying facial proportions',recipe['effective_prompt'])
        self.assertEqual(recipe['inspiration_name'],'Pikachu')
        self.assertEqual(recipe['inspiration_recipe_version'],'1.1')

    def test_every_named_target_compiles_for_modern_generator(self):
        with patch('app.prompting.translate_prompt',return_value=('', 'none')),patch('app.model_registry.validate_selection',return_value=[512,512]):
            for identifier,item in ENTRIES.items():
                with self.subTest(target=identifier):
                    recipe=compile_studio_prompt('cinema','',model_id='flux_klein',inspiration_id=identifier)
                    self.assertEqual(recipe['inspiration_name'],item['name'])
                    self.assertIn(item['features'],recipe['effective_prompt'])
                    self.assertEqual(recipe['inspiration_category'],item['category'])

    def test_ranking_is_category_scoped_and_returns_alternatives(self):
        ids=np.asarray(list(ENTRIES)); vectors=np.ones((len(ids),2),dtype=np.float32)/np.sqrt(2)
        first=rank('pokemon',[1,1],ids,vectors,vectors)
        self.assertEqual(len(first),3)
        self.assertTrue(all(key.startswith('pokemon:') for key,_ in first))
        self.assertEqual(first,rank('pokemon',[1,1],ids,vectors,vectors))
        with self.assertRaises(ValueError):rank('invalid',[1,1],ids,vectors,vectors)

    def test_affinity_respects_generation_lock_before_loading_model(self):
        with patch('app.engine._lock') as lock,patch('app.discovery_matcher.ClipSession') as model:
            lock.acquire.return_value=False
            with self.assertRaises(HTTPException) as error:match(b'not decoded','pokemon')
            self.assertEqual(error.exception.status_code,409)
            model.assert_not_called()

    def test_assignment_preserves_photo_and_compares_only_face(self):
        from PIL import Image
        face=Image.new('RGB',(64,64),'white')
        ids=np.asarray(list(ENTRIES))
        vectors=np.ones((len(ids),2),dtype=np.float32)/np.sqrt(2)
        with patch('app.engine._lock') as lock, patch('app.influencer_engine.face_crop',return_value=(face,{'x':10,'y':20,'width':64,'height':64})) as crop, patch('app.discovery_matcher.ClipSession') as session, patch('app.discovery_matcher.reference_index',return_value=(ids,vectors,vectors)):
            lock.acquire.return_value=True
            session.return_value.__enter__.return_value.images.return_value=np.asarray([[1.,1.]])/np.sqrt(2)
            result=match(b'original photo bytes','pokemon')
            crop.assert_called_once_with(b'original photo bytes',reference_context=1.1)
            session.return_value.__enter__.return_value.images.assert_called_once_with([face])
            self.assertEqual(result['assigned_character']['id'],result['suggestions'][0]['id'])
            self.assertFalse(result['photo_modified'])
            self.assertEqual(result['query_region'],'face')
            lock.release.assert_called_once()
