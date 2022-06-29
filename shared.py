import time
import computer
import sd.chronology as chronos

VERBOSE = 1

START_TIME = time.time()
COMP = computer.Computer()
LOG_DIR = '/tmp/log_dir'

def aprint(*args, v=1, header='\n', **kargs):
    if VERBOSE >= v:
        print(header + chronos.local_time(), *map(str, args), **kargs)
