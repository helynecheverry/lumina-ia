"""Reentrant thread + process lock for models sharing this machine's resources."""
import fcntl
import threading
from pathlib import Path


class ResourceLock:
    def __init__(self,path):
        self.path=Path(path)
        self.thread_lock=threading.RLock()
        self.file=None
        self.owner=None
        self.depth=0

    def acquire(self,blocking=True):
        if not self.thread_lock.acquire(blocking=blocking):return False
        if self.owner==threading.get_ident():
            self.depth+=1
            return True
        file=None
        try:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            file=self.path.open('a+b')
            fcntl.flock(file,fcntl.LOCK_EX|(0 if blocking else fcntl.LOCK_NB))
            self.file=file;self.owner=threading.get_ident();self.depth=1
            return True
        except BlockingIOError:
            if file:file.close()
            self.thread_lock.release()
            return False
        except BaseException:
            if file:file.close()
            self.thread_lock.release()
            raise

    def release(self):
        if self.owner!=threading.get_ident():raise RuntimeError('Resource lock is not owned by this thread')
        self.depth-=1
        if not self.depth:
            try:fcntl.flock(self.file,fcntl.LOCK_UN)
            finally:
                self.file.close();self.file=None;self.owner=None
        self.thread_lock.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self,*args):self.release()
