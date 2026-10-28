"""Age regression must use an explicit age and a reference-image editor."""
import unittest
from unittest.mock import patch
from app.youth import validate_target_age
from app.prompting import compile_studio_prompt


class YouthTest(unittest.TestCase):
    def test_invalid_ages_are_rejected(self):
        for age in (True, 7, 18, 100, 14.5, '14'):
            with self.subTest(age=age), self.assertRaises(ValueError):
                validate_target_age(age)

    def test_age_recipe_bypasses_translation_and_costume_defaults(self):
        with patch('app.model_registry.validate_selection', return_value=[512,512]), patch('app.prompting.translate_prompt') as translator:
            for age in (8,10,12,14,16,17):
                recipe=compile_studio_prompt('editorial',model_id='flux_klein',target_age=age)
                self.assertIn(f'{age} years old',recipe['effective_prompt'])
                self.assertIn('SAME person',recipe['effective_prompt'])
                self.assertIn('reference face',recipe['effective_prompt'])
                self.assertEqual(recipe['target_age'],age)
                self.assertEqual(recipe['creation_mode'],'youth')
                self.assertNotIn('fashion editorial',recipe['effective_prompt'])
            translator.assert_not_called()

    def test_unsupported_engine_does_not_fall_back_to_text_generation(self):
        with patch('app.model_registry.validate_selection',return_value=[512,512]):
            with self.assertRaises(ValueError):
                compile_studio_prompt('editorial',target_age=14)
