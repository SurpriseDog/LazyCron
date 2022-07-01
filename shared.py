import time
import computer
import sd.chronology as chronos

VERBOSE = 1

START_TIME = time.time()
COMP = computer.Computer()
LOG_DIR = '/tmp/log_dir'
NICE = 5

# Low values to suspend computer or run scheduled procesess
LOW_NET = 10e3
LOW_CPU = 10
LOW_DISK = 1e6

def aprint(*args, v=1, header='\n', **kargs):
    if VERBOSE >= v:
        print(header + chronos.local_time(), *map(str, args), **kargs)
