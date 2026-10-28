"""Text-request precedence and non-transforming requests must remain distinct."""
import unittest
from unittest.mock import patch
from app.transformation_intent import resolve_character
from app.prompting import compile_prompt, compile_studio_prompt


class TransformationIntentTest(unittest.TestCase):
    def test_snake_request_overrides_selected_fox_without_combining_species(self):
        recipe=compile_prompt('editorial','quiero generar una serpiente humana',translated='I want to generate a human snake',character_type='fox')
        self.assertEqual(recipe['resolved_character_type'],'snake')
        self.assertEqual(recipe['character_label'],'Serpiente humana')
        self.assertIn('reptilian scales',recipe['effective_prompt'])
        self.assertIn('vertical black slit pupils',recipe['effective_prompt'])
        for conflict in ['fox ears','orange and cream fur','natural human appearance','elegant designer jacket']:
            self.assertNotIn(conflict,recipe['effective_prompt'])

    def test_unknown_creature_is_not_limited_to_named_expansions(self):
        for original,english in [('ajolote humano','human axolotl'),('híbrido de cristal','crystal hybrid')]:
            with self.subTest(text=original):
                recipe=compile_prompt('editorial',original,translated=english)
                self.assertTrue(recipe['custom_character'])
                self.assertEqual(recipe['resolved_character_type'],'freeform')
                self.assertIn(english,recipe['effective_prompt'])
                self.assertNotIn('natural human appearance',recipe['effective_prompt'])

    def test_regular_clothes_background_and_negations_do_not_transform_person(self):
        for text in ['red jacket','a shirt with a printed snake','background with snakes', 'sin serpientes', 'no quiero ser serpiente', 'do not want to be a snake','sin escamas de serpiente','no quiero serpiente','adventure portrait']:
            with self.subTest(text=text):
                _,intent=resolve_character('natural',text,text)
                self.assertFalse(intent['custom_character'])

    def test_intensity_changes_reference_bounds(self):
        subtle,_=resolve_character('natural','serpiente humana sutil','subtle human snake')
        strong,_=resolve_character('natural','serpiente humana extrema','strong human snake')
        self.assertGreater(subtle['max_identity'],strong['max_identity'])
        self.assertIn('pronounced',strong['edit_scope'])

    def test_custom_outfit_and_scene_are_still_applied(self):
        recipe=compile_prompt('editorial','serpiente humana',translated='human snake',appearance={'outfit':'red_jacket','scene':'forest'})
        self.assertIn('red jacket',recipe['effective_prompt'])
        self.assertIn('enchanted forest',recipe['effective_prompt'])

    def test_modern_instruction_allows_requested_eye_and_skin_changes(self):
        with patch('app.prompting.translate_prompt',return_value=('human snake','es')),patch('app.model_registry.validate_selection',return_value=[512,512]):
            recipe=compile_studio_prompt('editorial','serpiente humana',model_id='flux_klein')
        self.assertTrue(recipe['custom_character'])
        self.assertIn('reptilian scales',recipe['effective_prompt'])
        self.assertIn('slit pupils',recipe['effective_prompt'])
        self.assertNotIn('animal around',recipe['effective_prompt'])
        self.assertNotIn('Keep the original human face shape, eyes, nose',recipe['effective_prompt'])
        self.assertLess(len(recipe['effective_prompt'].split()),220)

    def test_explicit_colors_override_inferred_creature_colors(self):
        recipe=compile_prompt('editorial','serpiente humana roja',translated='human snake with red scales and blue eyes')
        self.assertEqual(recipe['inferred_details'],[])
        self.assertNotIn('green reptilian',recipe['effective_prompt'])
        self.assertNotIn('yellow reptilian',recipe['effective_prompt'])

    def test_full_body_does_not_receive_conflicting_head_and_shoulders_crop(self):
        with patch('app.prompting.translate_prompt',return_value=('human snake full body','en')),patch('app.model_registry.validate_selection',return_value=[512,768]):
            recipe=compile_studio_prompt('editorial','serpiente humana de cuerpo entero',model_id='flux_klein',framing='portrait')
        self.assertEqual(recipe['composition'],'full_body')
        self.assertIn('head to feet',recipe['effective_prompt'])
        self.assertNotIn('head and shoulders',recipe['effective_prompt'])

    def test_biological_term_is_preserved_before_translation(self):
        from app.prompting import protect_translation_terms
        protected=protect_translation_terms('Conviérteme en un ajolote humano con branquias externas rosas')
        self.assertIn('axolotl',protected)
        from app.prompting import normalize_translation_terms
        corrected=normalize_translation_terms('branquias externas','pink outer gills')
        self.assertIn('external gills',corrected)

    def test_known_creature_keeps_details_without_repeating_whole_animal_command(self):
        from app.prompting import character_detail_text, expand_visual_terms
        details=character_detail_text('Turn me into a human tiger with round ears and striped cheeks.','tiger')
        self.assertEqual(details,'round ears and striped cheeks')
        self.assertIn('branching',expand_visual_terms('pink external gills'))

    def test_color_on_species_name_also_overrides_default_skin_color(self):
        recipe=compile_prompt('editorial','serpiente humana roja',translated='red human snake')
        self.assertNotIn('green scales',recipe['inferred_details'])
        self.assertNotIn('green reptilian',recipe['effective_prompt'])

    def test_default_priority_is_intense_and_moderate_can_be_requested(self):
        profile,intent=resolve_character('natural','serpiente humana','human snake')
        self.assertEqual(intent['transformation_intensity'],'strong')
        self.assertEqual(profile['identity_mode'],'creature_with_identity_cues')
        _,intent=resolve_character('natural','serpiente humana marcada','moderate human snake')
        self.assertEqual(intent['transformation_intensity'],'visible')

    def test_visible_feature_does_not_reduce_default_intensity(self):
        _,intent=resolve_character('fox','tigre humano con bigotes visibles','human tiger with visible whiskers')
        self.assertEqual(intent['transformation_intensity'],'strong')


if __name__=='__main__':
    unittest.main()
