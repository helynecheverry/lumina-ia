import importlib.util,tempfile,unittest
from pathlib import Path
from PIL import Image
spec=importlib.util.spec_from_file_location('audit',Path(__file__).resolve().parents[1]/'scripts/audit_edit_training.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class EditTrainingAuditTest(unittest.TestCase):
 def test_duplicate_references_never_leak_into_validation(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'reference').mkdir();(root/'target').mkdir()
   for name,color in [('a','red'),('b','red'),('c','blue')]:
    Image.new('RGB',(32,32),color).save(root/'reference'/(name+'.png'))
    Image.new('RGB',(32,32),'green').save(root/'target'/(name+'.png'))
    (root/'target'/(name+'.txt')).write_text('Turn the subject green')
   report=module.audit(root);self.assertTrue(report['data_ready'])
   assignments={pair['id']:pair['split'] for pair in report['pairs']}
   self.assertEqual(assignments['a'],assignments['b']);self.assertNotEqual(assignments['a'],assignments['c'])
 def test_unchanged_targets_and_missing_instructions_are_rejected(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'reference').mkdir();(root/'target').mkdir()
   for name in ['a','b']:
    for part in ['reference','target']:Image.new('RGB',(32,32),'red').save(root/part/(name+'.png'))
   (root/'target/a.txt').write_text('Transform this person')
   report=module.audit(root);self.assertFalse(report['data_ready']);self.assertEqual(report['valid_pairs'],0)
   self.assertTrue(any('idéntico' in error for error in report['errors']))
   self.assertTrue(any('instrucción' in error for error in report['errors']))
