#!/usr/bin/python3
# Tell me how busy the device running the directory is.
# Requires: sudo apt-get install sysstat
# Exit 0 if device not busy
# Usage ./how_busy folder_name

import re
import os
import sys
import time
import itertools

from sd.columns import auto_cols
from sd.common import avg, sorted_array, flatten, check_install, percent, list_get, quickrun, DotDict, spawn

# Kib vs KB
# iostat uses KiB: https://man7.org/linux/man-pages/man1/iostat.1.html
# sar uses KiB: https://man7.org/linux/man-pages/man1/sar.1.html
# All numbers are converted to base units of bytes for simplicity

def is_device_busy(dev, wait=2, reps=4, verbose=0):
    "Check how busy the device is"
    if reps < 2:
        reps = 2

    usage = []
    get_ready = False     # next line contains the percentage
    for line in quickrun('nice', 'iostat', '-d', '-x', dev, wait, reps + 1, verbose=verbose):
        val = re.split(' +', line)[-1]
        if get_ready:
            usage.append(float(val))
        get_ready = bool(val == '%util')
    # print(dev+':', usage[1:], '=', percent(avg(usage[1:])))
    return int(avg(usage[1:]) * 1024)





def all_disk_usage(wait=2, reps=4, verbose=0, ignore_links=True):
    '''Return total i/o for all devices in Bytes / second
    ignore_links will ignore loop and dm-? devs for total'''

    ready = False
    total = 0
    table = dict()
    rep = -1
    for line in quickrun('nice', 'iostat', '-d', wait, reps + 1, verbose=verbose):
        if verbose >= 2:
            print(rep, line)
        if not line:
            continue
        if line.startswith('Device'):
            ready = True
            rep += 1
            continue
        if ready and rep > 0:
            # Skip the first rep because it contains bad data
            line = line.split()
            dev = line[0]
            usage = sum(map(float, line[2:4]))
            table.setdefault(dev, []).append(usage)
            if ignore_links and (dev.startswith('dm-') or dev.startswith('loop')):
                continue
            total += usage
    if verbose:
        out = [['Device'] + ['Rep ' + str(rep + 1) for rep in range(reps)] + ['', 'Average MB/s']]
        for dev in sorted(table.keys()):
            out.append([dev] + list(map(int, table[dev])))
            out[-1] += ['=', int(avg(table[dev]))]
        out = [out[0]] + list(sorted_array(out[1:], reverse=True))
        auto_cols(out, manual={-3: 2, -2: 2})
    return int(total / reps * 1024)


def get_network_usage(interval=1, samples=4, verbose=0):
    '''Return total network usage in Bytes / second, adds up rxkB/s and txkB/s columns from sar
    Requires: sudo apt install sysstat'''

    out = quickrun('sar', '-n', 'DEV', interval, samples, verbose=verbose)
    if verbose:
        auto_cols(map(str.split, out[-3:]))
    out = [line for line in out if line.startswith('Average:')]
    out = flatten([line.split()[4:6] for line in out[1:]])
    return int(sum(map(float, out)) * 1024)


def get_cpu_usage(interval=1, samples=4):
    out = quickrun(['mpstat', interval, samples])
    idle = out[-1].split()[-1]
    return 100 - float(idle)




def find_device(folder):
    "Given a directory, find the device"
    if os.path.isdir(folder):
        return quickrun(['df', folder])[1].split()[0]
    return None


def wait_until_not_busy(folder, threshold=11, wait=2, reps=8, delta=2, sleep=2):
    '''Threshold in % points
    Loop waiting until device isn't busy.
    every loop the threshold grows higher by delta'''

    dev = find_device(folder)
    print("Probing", dev)

    for x in itertools.count():
        usage = is_device_busy(dev, wait, reps)
        if usage * 100 < threshold:
            break
        else:
            print(percent(usage), '>', int(threshold))
        threshold += ((x + 1) * delta)
        time.sleep(x * sleep)


class Busy:
    "Poll the system to see if system is busy, returns None if value not ready yet"
    def __init__(self, expiration=100):
        self.expiration = expiration        # How long to keep values before querying again
        self.net = DotDict(que=None, thread=None, timestamp=0, value=None,)
        self.disk = DotDict(que=None, thread=None, timestamp=0, value=None,)
        self.cpu = DotDict(que=None, thread=None, timestamp=0, value=None,)

    def get_net(self, *args, **kargs):
        return self._query(self.net, get_network_usage, *args, **kargs)

    def get_disk(self, *args, **kargs):
        return self._query(self.disk, all_disk_usage, *args, **kargs)

    def get_cpu(self, *args, **kargs):
        return self._query(self.cpu, get_cpu_usage, *args, **kargs)


    def _query(self, vals, cmd, *args, **kargs):
        "Return a value if available, otherwise start a thread and return None while we wait"
        now = time.time()
        if now - vals.timestamp <= self.expiration:
            # print("Found existing value", vals.value)
            return vals.value
        else:
            if not vals.thread:
                # Start a thread
                # print("Spawning thread to check value")
                vals.que, vals.thread = spawn(cmd, *args, **kargs)
                return None
            else:
                # Check existing thread to see if it's done
                if vals.thread.is_alive():
                    # print("Thread still running")
                    return None
                else:
                    vals.thread = None
                    vals.value = vals.que.get()
                    # print("Value ready:", vals.value)
                    vals.timestamp = now
                    return vals.value


if __name__ == "__main__":
    check_install('iostat', msg='sudo apt-get install sysstat')
    wait_until_not_busy(list_get(sys.argv, 1, '/home'))
