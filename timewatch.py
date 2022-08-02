#!/usr/bin/python3

import time
import subprocess

import shared
from sd.common import warn
from sd.chronology import local_time, fmt_time, msleep





def get_idle():
    "Run a command to get the system idle time"
    if shared.PLATFORM == 'linux':
        val = subprocess.run('xprintidle', check=True, stdout=subprocess.PIPE)
        return float(val.stdout.strip()) / 1000
    else:
        warn("Can't fetch idle on Unknown platform", shared.PLATFORM)
        return 0


class TimeWatch:
    "Keep track of idle time, even when computer sleeps"

    def __init__(self, verbose=0):
        self.idle = 0                           # Seconds of idle time
        self.elapsed = 0                        # Total time Computer has spent in usage
        self.increase = 0                       # Increase in elapsed from last call
        self._inuse_start = 0                       # Contiguous usage time start
        self.today_elapsed = 0                  # Elapsed just for today
        self.verbose = verbose

    def reset(self):
        "Reset counters on new day"
        self.idle = 0
        self.today_elapsed = 0

    def usage(self):
        "Time computer in use without breaks"
        if self._inuse_start:
            return time.time() - self._inuse_start
        else:
            return 0


    def sleep(self, seconds):
        "Sleep for seconds and track missing time"
        if seconds <= 0:
            return 0

        start = time.time()
        missing = msleep(seconds)
        end = time.time()

        # If there is missing time during sleep it most likely indicates computer went to sleep
        if missing / seconds > 0.05:
            if missing > seconds:
                self.idle = 0
                self._inuse_start = 0
            if self.verbose >= 2:
                shared.aprint("Unaccounted for time during", fmt_time(seconds), "sleep of",\
                              fmt_time(missing), "from", local_time(start), 'to', local_time(end))
        else:
            last = self.idle
            self.idle = get_idle()


            # Calculate the increase in idle time
            if self.idle > last:
                idle_increase = self.idle - last
            else:
                idle_increase = self.idle

            # Track usage time
            if idle_increase / seconds < 0.20:
                if not self._inuse_start:
                    self._inuse_start = start
            else:
                self._inuse_start = 0


            # Adjust the elapsed counters with in use time
            self.increase = max(seconds - idle_increase, 0)
            self.elapsed += self.increase
            self.today_elapsed += self.increase

            if self.verbose >= 4:
                self.status()

        return missing

    def status(self,):
        fmt = lambda x: fmt_time(x if x > 0.1 else 0, digits=2)
        print('\n' + local_time(),
              'Elapsed:', fmt(self.elapsed),
              'Today:', fmt(self.today_elapsed),
              'Idle:', fmt(self.idle),
              'Increase:', fmt(self.increase),
              'Usage:', fmt(self.usage())
              )


    def sleepy_time(self,):
        "Go to sleep without causing unaccounted for time"
        # quickrun('systemctl', 'suspend')
        subprocess.run(('systemctl', 'suspend'), check=False)
        self._inuse_start = 0
        self.idle = 0

def _tester():
    tw = TimeWatch(verbose=3)
    while True:
        tw.sleep(2)
        tw.status()

if __name__ == "__main__":
    _tester()
