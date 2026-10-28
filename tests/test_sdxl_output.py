"""Exercise the output boundary without expensive diffusion.

Actual GPU runs live in scripts/test_studio_model_browser.py. Here diffusion
alone is substituted so PNG conversion and provenance remain real code paths.
"""
import io
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from app import sdxl_engine


class SdxlOutputTest(unittest.TestCase):
    def test_decoded_pixels_become_png_with_consistent_provenance(self):
        reference = io.BytesIO()
        Image.new('RGB',(128,128),(100,120,140)).save(reference,'PNG')
        pixels = np.zeros((1,1024,768,3),dtype=np.float32)
        pixels[:,:,:,0]=.5
        with patch.object(sdxl_engine,'face_crop',return_value=(Image.new('RGB',(64,64)),{})), \
             patch.object(sdxl_engine.engine,'unload_engine'), \
             patch.object(sdxl_engine,'encode_text',return_value=()), \
             patch.object(sdxl_engine,'_encode_face',return_value=None), \
             patch.object(sdxl_engine,'diffuse',return_value=(None,'test-stub')), \
             patch.object(sdxl_engine,'decode',return_value=pixels), \
             patch.object(sdxl_engine,'_check_content'):
            output,meta=sdxl_engine.generate(reference.getvalue(),framing='portrait',steps=12)
        image=Image.open(io.BytesIO(output)).convert('RGB')
        self.assertEqual(image.size,(768,1024))
        self.assertEqual(image.getpixel((10,10)),(128,0,0))
        self.assertEqual(meta['model_id'],'portrait_sdxl')
        self.assertEqual(meta['framing'],'portrait')
        self.assertEqual(meta['source_repo'],'SG161222/RealVisXL_V5.0')
        self.assertEqual(meta['requested_size'],meta['output_size'])


if __name__=='__main__':
    unittest.main()
