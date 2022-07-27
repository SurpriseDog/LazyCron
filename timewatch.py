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
        self.today_elapsed = 0                  # Elapsed just for today
        self.verbose = verbose

    def reset(self):
        "Reset counters on new day"
        self.idle = 0
        self.today_elapsed = 0


    def sleep(self, seconds):
        "Sleep for seconds and track missing time"
        if seconds <= 0:
            return 0

        start = time.time()
        missing = msleep(seconds)
        end = time.time()


        if missing / seconds > 0.05:
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

            # Adjust the elapsed counters with in use time
            self.increase = max(seconds - idle_increase, 0)
            self.elapsed += self.increase
            self.today_elapsed += self.increase

            if self.verbose >= 4:
                self.status()

        return missing

    def status(self,):
        print('\n' + local_time(),
              'Elapsed:', fmt_time(self.elapsed),
              'Idle:', fmt_time(self.idle, digits=2),
              'Increase:', fmt_time(self.increase, digits=2),
              )


    def sleepy_time(self,):
        "Go to sleep without causing unaccounted for time"
        # quickrun('systemctl', 'suspend')
        subprocess.run(('systemctl', 'suspend'), check=False)
        self.idle = 0


if __name__ == "__main__":
    TW = TimeWatch(verbose=3)
    while True:
        TW.sleep(2)
