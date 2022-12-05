#!/usr/bin/python3
# how_busy functions coded with psutil
# All numbers are returned in bytes for simplicity

import time
import psutil


def get_cpu_usage(interval=1, samples=4):
    "Return cpu usage as percentage"
    total = 0
    for sample in range(samples):
        time.sleep(interval)                # Must sleep first to avoid counting python cpu usage
        cpu = psutil.cpu_percent()
        total += cpu
    return total / samples


def get_network_usage(interval=1, samples=4, verbose=0):
    '''Return total network usage in Bytes / second'''
    wait = interval * samples
    sent = psutil.net_io_counters().bytes_sent
    recv = psutil.net_io_counters().bytes_recv
    time.sleep(wait)
    total = psutil.net_io_counters().bytes_sent - sent
    total += psutil.net_io_counters().bytes_recv - recv
    return int(total / wait)


def all_disk_usage(interval=2, reps=4, verbose=0, ignore_links=True):
    '''Return total i/o for all devices in Bytes / second'''
    wait = reps * interval

    '''
    start = psutil.disk_io_counters(perdisk=True)
    time.sleep(wait)
    end = psutil.disk_io_counters(perdisk=True)
    total = 0
    for dev in end.keys():
        if ignore_links and (dev.startswith('dm-') or dev.startswith('loop')):
                        continue
        extra = end[dev].read_bytes - start[dev].read_bytes
        extra += end[dev].write_bytes - start[dev].write_bytes
        print(dev, extra)
        total += extra
    '''
    start = psutil.disk_io_counters()
    time.sleep(wait)
    end = psutil.disk_io_counters()
    total = end.read_bytes - start.read_bytes
    total += end.write_bytes - start.write_bytes
    return int(total / wait)



def test():
    print("psutil Disk Usage (MB/S):", all_disk_usage() / 1e6)
    print("psutil Cpu Usage:", get_cpu_usage())
    print("psutil Network Usage:", get_network_usage())





if __name__ == "__main__":
    test()
