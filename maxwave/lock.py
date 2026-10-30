"""A real OS lock; a stale PID file cannot block startup or kill another process."""
import os
from .common import STATE
class RunningLock:
 def __enter__(self):
  STATE.mkdir(exist_ok=True);self.f=(STATE/'bridge.lock').open('a+b');self.f.seek(0)
  if os.name=='nt':
   import msvcrt
   if self.f.read(1)==b'':self.f.write(b' ');self.f.flush()
   self.f.seek(0)
   try:msvcrt.locking(self.f.fileno(),msvcrt.LK_NBLCK,1)
   except OSError:self.f.close();raise BlockingIOError('Мост уже запущен.')
  else:
   import fcntl
   try:fcntl.flock(self.f,fcntl.LOCK_EX|fcntl.LOCK_NB)
   except OSError:self.f.close();raise BlockingIOError('Мост уже запущен.')
  return self
 def __exit__(self,*args):self.f.close()
def is_running():
 try:
  with RunningLock():return False
 except BlockingIOError:return True
