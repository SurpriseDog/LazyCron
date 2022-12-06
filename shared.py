import sys
import time

import computer
from sd.common import check_install, warn
import sd.chronology as chronos

VERBOSE = 1                         # Verbosity
SHOWPID = False                     # Set to true to print PID of each process (experimental)

START_TIME = time.time()
COMP = computer.Computer()
LOG_DIR = '/tmp/log_dir'            # Default Log Directory
NICE = 0                            # Script nice value (subprocesses can be higher)

# Low values to suspend computer or run scheduled procesess
LOW_NET = 10e3
LOW_CPU = 10
LOW_DISK = 1e6

def aprint(*args, v=1, header='\n', **kargs):
    if VERBOSE >= v:
        print(header + chronos.local_time(), *map(str, args), **kargs)


# Choose correct program to get idle time and verify it is installed
if sys.platform.startswith('win'):
    PLATFORM = 'windows'
    warn("Windows implementation not implemented")
elif sys.platform.startswith('linux'):
    PLATFORM = 'linux'
else:
    warn("Unknown computer system:", sys.platform)
