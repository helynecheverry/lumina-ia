import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from app.resource_lock import ResourceLock


class ResourceLockTest(unittest.TestCase):
    def test_reentrant_and_excludes_another_process(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'models.lock'
            lock=ResourceLock(path)
            code='from app.resource_lock import ResourceLock; import sys; lock=ResourceLock(sys.argv[1]); sys.exit(0 if lock.acquire(blocking=False) else 7)'
            with lock:
                self.assertTrue(lock.acquire(blocking=False))
                lock.release()
                result=subprocess.run([sys.executable,'-c',code,str(path)],timeout=10)
                self.assertEqual(result.returncode,7)
            result=subprocess.run([sys.executable,'-c',code,str(path)],timeout=10)
            self.assertEqual(result.returncode,0)
