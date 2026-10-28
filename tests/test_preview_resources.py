"""Prevent a translator load alongside diffusion in concurrent HTTP requests."""
import threading
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from app.api import PromptPreview, compile_preview_safely, _lock


class PreviewResourcesTest(unittest.TestCase):
    def test_busy_gpu_work_rejects_preview_before_loading_translator(self):
        held=threading.Event()
        release=threading.Event()
        def busy():
            with _lock:
                held.set()
                release.wait(10)
        thread=threading.Thread(target=busy)
        thread.start()
        self.assertTrue(held.wait(5))
        try:
            with patch('app.api.compile_studio_prompt') as compiler:
                with self.assertRaises(HTTPException) as error:
                    compile_preview_safely(PromptPreview(preset='professional',prompt='Traje negro'))
                self.assertEqual(error.exception.status_code,409)
                compiler.assert_not_called()
        finally:
            release.set()
            thread.join(5)


if __name__=='__main__':
    unittest.main()
