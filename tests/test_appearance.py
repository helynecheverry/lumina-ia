import unittest
from fastapi import HTTPException
from app.appearance import validate_appearance
from app.prompting import compile_prompt
from app.character_types import CHARACTER_TYPES


class AppearanceTest(unittest.TestCase):
    def test_panel_values_override_conflicting_style_defaults(self):
        appearance={'presentation':'masculine','outfit':'red_jacket','scene':'blue_studio','lighting':'dramatic'}
        recipe=compile_prompt('editorial',translated='',appearance=appearance)
        for text in ['masculine presentation','red jacket','plain blue studio background','dramatic cinematic lighting']:
            self.assertIn(text,recipe['effective_prompt'])
        for text in ['elegant designer jacket','warm neutral background','soft studio light']:
            self.assertNotIn(text,recipe['effective_prompt'])
        self.assertEqual(recipe['appearance'],appearance)

    def test_free_text_overrides_a_contradictory_panel_choice(self):
        recipe=compile_prompt('editorial',translated='blue jacket',appearance={'outfit':'red_jacket'})
        self.assertIn('blue jacket',recipe['effective_prompt'])
        self.assertNotIn('red jacket',recipe['effective_prompt'])
        self.assertEqual(recipe['ignored_selections'],['outfit'])

    def test_invalid_control_or_value_is_rejected(self):
        for value in [{'no_such_control':'red'},{'outfit':'anything'},{'lighting':22},[]]:
            with self.assertRaises(ValueError):validate_appearance(value)

    def test_character_catalog_has_distinct_applied_types(self):
        self.assertGreaterEqual(len(CHARACTER_TYPES),10)
        recipes=[compile_prompt('editorial',translated='',character_type=key) for key in CHARACTER_TYPES]
        self.assertEqual(len({r['character_direction'] for r in recipes}),len(CHARACTER_TYPES))
        for key in ('cat','fox','dragon','bird','alien'):
            recipe=compile_prompt('editorial',translated='',character_type=key)
            self.assertEqual(recipe['backbone'],'photo')
            self.assertIn('recognizable human',recipe['effective_prompt'])
            self.assertNotIn('human skin',recipe['negative_prompt'])
            self.assertEqual(recipe['identity_mode'],'preserve_human_face')

    def test_every_character_preserves_human_identity_in_modern_editing(self):
        from app.prompting import compile_studio_prompt
        for key in CHARACTER_TYPES:
            with self.subTest(character=key):
                recipe=compile_studio_prompt('professional',model_id='flux_klein',character_type=key)
                self.assertIn('Preserve the identity and facial features of this exact person',recipe['effective_prompt'])
                self.assertIn('localized enhancements',recipe['effective_prompt'])
                self.assertNotIn('Prioritize the requested character anatomy',recipe['effective_prompt'])
                self.assertNotIn('human skin',recipe['negative_prompt'])
                self.assertNotIn('human nose',recipe['negative_prompt'])
                self.assertGreaterEqual(CHARACTER_TYPES[key]['max_identity'],1.0)

    def test_animal_types_are_partial_human_transformations(self):
        for key in ('cat','fox','dragon','bird','alien'):
            recipe=compile_prompt('professional',translated='',character_type=key)
            self.assertIn('original human',recipe['effective_prompt'])
            self.assertNotIn('anthropomorphic',recipe['effective_prompt'])
            self.assertGreaterEqual(CHARACTER_TYPES[key]['min_identity'],.65)
