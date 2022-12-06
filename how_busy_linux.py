#!/usr/bin/python3
# how_busy functions for linux only

# Kib vs KB
# iostat uses KiB: https://man7.org/linux/man-pages/man1/iostat.1.html
# sar uses KiB: https://man7.org/linux/man-pages/man1/sar.1.html
# All numbers are converted to base units of bytes for simplicity


import shutil
from sd.columns import auto_cols
from sd.common import avg, sorted_array, flatten, quickrun, DotDict




# See what commands are available
AVAIL = DotDict()
for cmd, msg in dict(mpstat='CPU monitoring will not function.',
                     sar='Network monitor will not function.',
                     iostat='Disk usage monitor will not function.',
                     ).items():
    if not shutil.which(cmd):
        print('Warning!', cmd, 'is not available.', msg)
        AVAIL[cmd] = False
    else:
        AVAIL[cmd] = True



def get_cpu_usage(interval=1, samples=4):
    if not AVAIL.mpstat:
        return 0
    out = quickrun(['mpstat', interval, samples])
    idle = out[-1].split()[-1]
    return 100 - float(idle)


def get_network_usage(interval=1, samples=4, verbose=0):
    '''Return total network usage in Bytes / second, adds up rxkB/s and txkB/s columns from sar
    Requires: sudo apt install sysstat'''
    if not AVAIL.sar:
        return 0

    out = quickrun('sar', '-n', 'DEV', interval, samples, verbose=verbose)
    if verbose:
        auto_cols(map(str.split, out[-3:]))
    out = [line for line in out if line.startswith('Average:')]
    out = flatten([line.split()[4:6] for line in out[1:]])
    return int(sum(map(float, out)) * 1024)


def all_disk_usage(interval=2, reps=4, verbose=0, ignore_links=True):
    '''Return total i/o for all devices in Bytes / second
    ignore_links will ignore loop and dm-? devs for total'''
    if not AVAIL.iostat:
        return 0

    ready = False
    total = 0
    table = dict()
    rep = -1
    for line in quickrun('nice', 'iostat', '-d', interval, reps + 1, verbose=verbose):
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





'''
def get_device_usage(dev, wait=2, reps=4, verbose=0):
    "Check how busy the device is"
    if reps < 2:
        reps = 2

    usage = []
    get_ready = False     #next line contains the percentage
    for line in quickrun('nice', 'iostat', '-d', '-x', dev, wait, reps + 1, verbose=verbose):
        val = re.split(' +', line)[-1]
        if get_ready:
            usage.append(float(val))
        get_ready = bool(val == '%util')
    # print(dev+':', usage[1:], '=', percent(avg(usage[1:])))
    return int(avg(usage[1:]) * 1024)

def wait_until_not_busy(folder, threshold=11, wait=2, reps=8, delta=2, sleep=2):
    "Threshold in % points
    Loop waiting until device isn't busy.
    every loop the threshold grows higher by delta"

    dev = find_device(folder)
    print("Probing", dev)

    for x in itertools.count():
        usage = get_device_usage(dev, wait, reps)
        if usage * 100 < threshold:
            break
        else:
            print(percent(usage), '>', int(threshold))
        threshold += ((x + 1) * delta)
        time.sleep(x * sleep)
'''

def test():
    print('Utilities available:', AVAIL)
    print("Disk Usage (MB/S):", all_disk_usage() / 1e6)
    print("Cpu Usage:", get_cpu_usage())
    print("Network Usage:", get_network_usage())


if __name__ == "__main__":
    test()
