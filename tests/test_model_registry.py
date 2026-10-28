"""Model compatibility and resource guards; no diffusion tensors are loaded."""
import unittest
from unittest.mock import patch

from app.model_registry import validate_selection, model_status


class ModelRegistryTest(unittest.TestCase):
    def test_framing_is_specific_to_the_architecture(self):
        self.assertEqual(validate_selection('portrait_sd15','portrait'),[512,768])
        self.assertEqual(validate_selection('portrait_sdxl','portrait'),[768,1024])
        with self.assertRaises(ValueError):
            validate_selection('portrait_sdxl','unbounded')
        with self.assertRaises(ValueError):
            validate_selection('../../model','square')

    def test_modern_models_are_not_ready_on_current_resource_profile(self):
        hw={'cuda':True,'vram_gb':4,'ram_gb':8}
        for name in ('flux_klein','qwen_edit'):
            result=model_status(name,hw)
            self.assertFalse(result['ready'])
            self.assertIn('no alcanza',result['reason'])
            self.assertFalse(result['tested'])

    def test_missing_weights_are_not_ready_even_with_a_large_gpu(self):
        with patch('app.model_registry.Path.is_file',return_value=False):
            result=model_status('portrait_sdxl',{'cuda':True,'vram_gb':24,'ram_gb':64})
        self.assertFalse(result['installed'])
        self.assertFalse(result['ready'])
        self.assertTrue(result['missing_files'])


if __name__ == '__main__':
    unittest.main()
