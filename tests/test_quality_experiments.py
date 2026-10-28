"""Verify private experiment provenance and recovery without GPU inference."""
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

spec = importlib.util.spec_from_file_location('quality', Path(__file__).resolve().parents[1]/'scripts/run_quality_experiments.py')
quality = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quality)


class QualityExperimentsTest(unittest.TestCase):
    def test_report_keeps_results_from_other_case_files_and_escapes_review(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)
            for name in ('first', 'second'):
                folder=out/name;folder.mkdir()
                quality.save(folder/'record.json', {'case':{'id':name},'status':'completed', 'review':{'note':'<script>alert(1)</script>'}})
            quality.report(out,[{'id':'second'}])
            page=(out/'index.html').read_text()
            self.assertIn('first/result.png',page)
            self.assertIn('second/result.png',page)
            self.assertNotIn('<script>',page)

    def test_completed_case_is_resumed_without_another_submission(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)
            source=out/'reference.png';Image.new('RGB',(10,10),'blue').save(source)
            quality.save(out/'session.json',{})
            case={'id':'done'};folder=out/'done';folder.mkdir()
            quality.save(folder/'record.json',{'case':case,'status':'completed'})
            quality.save(out/'cases.json',[case])
            argv=['runner','--reference',str(source),'--cases',str(out/'cases.json'),'--out',str(out)]
            with patch('sys.argv',argv),patch.object(quality.requests,'Session') as session:
                quality.main()
                session.return_value.post.assert_not_called()
            self.assertTrue((out/'index.html').exists())

    def test_existing_session_rejects_a_different_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory);source=out/'another.png'
            Image.new('RGB',(10,10),'red').save(source)
            Image.new('RGB',(10,10),'blue').save(out/'reference.png')
            quality.save(out/'cases.json',[{'id':'one'}])
            argv=['runner','--reference',str(source),'--cases',str(out/'cases.json'),'--out',str(out)]
            with patch('sys.argv',argv),self.assertRaisesRegex(ValueError,'referencias distintas'):
                quality.main()


if __name__ == '__main__':
    unittest.main()
