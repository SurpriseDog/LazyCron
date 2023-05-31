import sys
import time

import computer
from sd.common import warn
import sd.chronology as chronos

VERBOSE = 1                         # Verbosity

START_TIME = time.time()
COMP = computer.Computer()
if COMP.batt_capacity or not COMP.lid_state:
    print("Disregard these messages if you are running on a laptop system.")

LOG_DIR = '/tmp/log_dir'            # Default Log Directory

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
elif sys.platform.startswith('mac'):
    PLATFORM = 'mac'
    warn("mac implementation not implemented")
elif sys.platform.startswith('linux'):
    PLATFORM = 'linux'
else:
    warn("Unknown computer system:", sys.platform)
