#!/usr/bin/python3

import sys
import time
import subprocess
from sd.common import rint, check_install, error, spawn
from sd.chronology import local_time, fmt_time, msleep

import shared

# Choose correct program to get idle time and verify it is installed
if sys.platform.startswith('win'):
    PLATFORM = 'windows'
    error("Windows implementation not implemented")
elif sys.platform.startswith('linux'):
    PLATFORM = 'linux'
    check_install('xprintidle', msg="sudo apt install xprintidle")
else:
    error("Unknown computer system:", sys.platform)


class TimeWatch:
    "Keep track of idle time, even when computer sleeps"

    def __init__(self, verbose=0):
        self._raw = 0                           # Raw idle number read from system
        self.idle = 0                           # Seconds of idle from last sleep
        self.last = 0                           # Last idle returned
        self.elapsed = 0                        # Total time Computer has spent not idle
        self.verbose = verbose

    def reset(self):
        self.idle = 0
        self._raw = 0
        self.last = 0

    def sleep(self, seconds):
        "Sleep for seconds and track missing time"
        if seconds <= 0:
            return 0
        start = time.time()
        missing = msleep(seconds)
        end = time.time()
        self.update_idle()

        if self.verbose >= 2 and missing / seconds > 0.01:
            shared.aprint("Unaccounted for time during", fmt_time(seconds), "sleep:", fmt_time(missing), end, start)

        return missing


    def update_idle(self,):
        "Query system to get idle time"
        self.last = self._raw

        if PLATFORM == 'linux':
            val = subprocess.run('xprintidle', check=True, stdout=subprocess.PIPE)
            val = float(val.stdout.strip()) / 1000
            self._raw = val
        else:
            error("Unknown platform", PLATFORM)


        if self._raw > self.last:
            self.idle = self._raw - self.last
        else:
            self.idle = self._raw
        self.elapsed += self.idle

        if self.verbose >= 3:
            print(local_time(), 'Elapsed:', fmt_time(self.elapsed), 'Idle:', rint(self.idle), 'Raw:', rint(self._raw))

    def sleepy_time(self,):
        "Go to sleep without causing unaccounted for time"
        # quickrun('systemctl', 'suspend')
        subprocess.run(('systemctl', 'suspend'), check=True)
        self.elapsed = 0


if __name__ == "__main__":
    TW = TimeWatch(verbose=3)
    while True:
        TW.sleep(2)
