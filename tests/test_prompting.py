import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.prompting import compile_prompt, encode_complete_prompt, translate_prompt
from app.style_catalog import PRESETS

class PromptingTest(unittest.TestCase):
    def test_recipes_have_real_distinct_directions(self):
        self.assertEqual(len(PRESETS),32)
        self.assertEqual(len({r['prompt'] for r in PRESETS.values()}),32)
        for key in PRESETS:
            recipe=compile_prompt(key,'',translated='')
            self.assertIn(PRESETS[key]['prompt'],recipe['effective_prompt'])
            self.assertTrue(recipe['negative_prompt'])

    def test_custom_clothes_override_default(self):
        recipe=compile_prompt('editorial','Chaqueta roja',translated='red jacket')
        self.assertTrue(recipe['effective_prompt'].startswith('red jacket'))
        self.assertNotIn('designer jacket',recipe['effective_prompt'])
        self.assertEqual(recipe['original_prompt'],'Chaqueta roja')

    def test_spanish_is_translated_locally(self):
        result,language=translate_prompt('Llevo una chaqueta roja y un sombrero azul')
        self.assertEqual(language,'es')
        self.assertIn('red',result.lower())
        self.assertIn('blue',result.lower())

    def test_short_spanish_instruction_is_not_missed(self):
        result,language=translate_prompt('atardecer')
        self.assertEqual(language,'es')
        self.assertNotEqual(result.lower(),'atardecer')
        self.assertTrue(result)

    def test_character_type_changes_visual_direction(self):
        natural=compile_prompt('editorial',translated='',character_type='natural')
        bold=compile_prompt('editorial',translated='',character_type='bold')
        extreme=compile_prompt('editorial',translated='',character_type='extreme')
        self.assertNotIn('purple',natural['effective_prompt'])
        self.assertIn('avant-garde',bold['effective_prompt'])
        self.assertIn('exaggerated',extreme['effective_prompt'])
        self.assertNotIn('purple',bold['effective_prompt'])
        self.assertNotIn('neon green',extreme['effective_prompt'])
        self.assertEqual(bold['character_label'],'Atrevido')
        self.assertNotEqual(natural['effective_prompt'],bold['effective_prompt'])

    def test_explicit_user_hair_overrides_character_hair(self):
        recipe=compile_prompt('editorial','Pelo rojo',translated='red hair',character_type='bold')
        self.assertIn('red hair',recipe['effective_prompt'])
        self.assertNotIn('purple',recipe['effective_prompt'])
        self.assertNotIn('purple',recipe['character_direction'])

    def test_model_preview_matches_edit_instruction_and_framing(self):
        from app.prompting import compile_studio_prompt
        recipe=compile_studio_prompt('professional','',model_id='qwen_edit',framing='portrait')
        self.assertTrue(recipe['effective_prompt'].startswith('Transform the reference person'))
        self.assertIn('vertical upper body',recipe['effective_prompt'])
        self.assertEqual(recipe['requested_size'],[768,1024])

    def test_context_includes_tail_after_first_window(self):
        import torch
        class Tokenizer:
            model_max_length=77; bos_token_id=1;eos_token_id=2;pad_token_id=0
            def __call__(self,text,**kwargs):
                class Output:pass
                output=Output();output.input_ids=[int(item) for item in text.split()];return output
        class Pipe:
            tokenizer=Tokenizer();_execution_device='cpu'
            @staticmethod
            def text_encoder(ids):return (ids.unsqueeze(-1).float(),)
        positive=' '.join(str(i) for i in range(10,200))
        pos,neg,count=encode_complete_prompt(Pipe(),positive,'3 4')
        self.assertEqual(count,3)
        self.assertEqual(pos.shape,neg.shape)
        self.assertTrue((pos==199).any(),'The final instruction must not be truncated')

if __name__=='__main__':unittest.main()
