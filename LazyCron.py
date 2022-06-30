#!/usr/bin/python3
# LazyCron - "Your computer will get around to it eventually."
# Usage: Run with -h for help.

################################################################################


import os
import re
import time
import shutil
import traceback

import shared
import how_busy
import scheduler

from shared import aprint
from timewatch import TimeWatch
from chronology import fmt_time, local_time

from sd.msgbox import msgbox
from sd.columns import auto_cols
from sd.easy_args import easy_parse
from sd.common import itercount, gohome, check_install, rfs, mkdir, warn, tman


def parse_args():
    "Parse arguments"
    positionals = [\
    ["schedule", '', str, 'schedule.txt'],
    "Filename to read schedule from."
    ]
    args = [\
    ['polling', 'polling_rate', float, 1],
    "How often to check (minutes)",
    ['idle', '', float, 0],
    "How long to wait before going to sleep (minutes) 0=Disable",
    ['verbose', '', int, 1],
    "What messages to print",
    ['testing', '', bool],
    "Do everything, but actually run the scripts.",
    ['logs', '', str, '/tmp/LazyCron_logs'],
    ['nice', '', int, 10],
    "Start processes with given Unix nice level\n(Higher values are nicer to other processes)",
    "Logging directory",
    ['skip', '', int, 0],
    "Don't run apps on startup, wait a bit.",
    ['stagger', '', float, 0],
    "Wait x minutes between starting programs.",
    ]
    args = easy_parse(args,
                      positionals,
                      usage='<schedule file>, options...',
                      description='Monitor the system for idle states and run scripts at the best time.')

    # Defaults if no value given
    if args.skip is None:
        args.skip = 1
    if args.verbose is None:
        args.verbose = 2
    return args


def is_busy(min_net=10e3, min_disk=1e6):
    '''
    Return True if disk or network usage above defaults
    min_net  = Network usage
    min_disk = Disk usage
    '''
    def fmt(num):
        return rfs(num)+'/s'

    net_usage = how_busy.get_network_usage(5, 4)
    if net_usage >= min_net:
        aprint("Busy: Network Usage:", fmt(net_usage))
        return True

    disk_usage = how_busy.all_disk_usage(5, 4)
    if disk_usage >= min_disk:
        aprint("Busy: Disk usage:", fmt(disk_usage))
        return True

    aprint("Not Busy - Network Usage:", fmt(net_usage), "Disk usage:", fmt(disk_usage))
    return False


def read_line(line, warn_score=5):
    "Given a line delimited by tabs and spaces, convert it to 5 fields"

    candidates = []
    # line = re.sub('\t', '    ', line)
    # Start with a large number of spaces (or any tabs) and reduce until the line is parsed
    for spaces in range(8, 1, -1):
        cols = re.split(r"\t+|\s{" + str(spaces) + ",}", line)
        # cols = re.split(r"\s{" + str(spaces) + ",}", line)
        cols = [item.strip() for item in cols if item]
        if len(cols) < 5:
            continue

        # Score each candidate based on spaces and tabs
        score = 10 - (len(cols) - 5) * 2        # 2 points off per extra field
        for item in cols[:4]:
            score -= item.count('  ') * 3       # double spaces inside field
            score -= item.count('\t') * 6       # tabs inside field
        candidates.append([score, cols])

    if not candidates:
        return False

    def print_can():
        for score, can in candidates:
            print(str(score) + ':', can)

    # Return the best scoring candidate
    candidates.sort()
    if shared.VERBOSE >= 3:
        print_can()
    score, cols = candidates[-1]

    # Bump up a low score if path is valid
    if score <= warn_score:
        path = cols[4].lstrip('#').strip().split()[:1]
        print("path =", path)
        if path and shutil.which(path[0]):
            score += 5

    if score <= warn_score:
        print_can()
        warn("Did I read this line correctly?")
        print('Source    :', repr(line))
        print('Conversion:', cols)
        print("Try using tabs instead of spaces if wrong")


    # If excess fields, combine the rest of the fields after 5 and return
    if len(cols) == 5:
        return cols
    else:
        path = line[line.index(cols[4]):]
        return cols[:4] + [path]


def read_schedule(schedule_apps, alert=warn):
    '''
    Read the schedule file,
    schedule_apps = List of Apps
    alert =         send messages to userspace with warn or msgbox
    '''
    new_sched = []
    headers = "time frequency date reqs path".split()

    with open(UA.schedule) as f:
        for line in f.readlines():
            # Ignore comments and empty lines
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # Find lines that have 5 fields in them
            print('\n' * 2)
            cols = read_line(line)
            if not cols:
                alert("Can't process line:", repr(line), "\nMake sure you put tabs in between columns")
                continue

            auto_cols([[item.title()+':' for item in headers], [repr(item) for item in cols], []])
            line = dict(zip(headers, cols))

            # Print the results and see if it matches an existing App
            # print("\n\n\n" + repr(line))
            for proc in schedule_apps:
                if line == proc.args:
                    print("Using existing App definition:", proc.name)
                    new_sched.append(proc)
                    break

            # Otherwise try to create a new one
            else:
                try:
                    proc = scheduler.App(line)
                except Exception as e:      # Bare exception to cover any processing errors
                    alert("Could not process line:", line)
                    traceback.print_exc()
                    print(e, '\n\n\n')
                    continue
                proc.add_reqs({'skip': UA.skip, 'nice' : UA.nice})
                proc.print()
                if proc.verify():
                    new_sched.append(proc)

    # Return the old version if new schedule has errors
    if not new_sched:
        return schedule_apps
    else:
        return new_sched


def main(verbose=1):
    polling_rate = 0                        # Time to rest at the end of every loop
    idle_sleep = UA.idle * 60               # Go to sleep after this long plugged in

    tw = TimeWatch(verbose=verbose)
    last_schedule_read = 0                  # last time the schedule file was read
    last_run = 0                            # Time when the last program was started
    schedule_apps = []                      # Apps found in schedule.txt
    cur_day = time.localtime().tm_yday      # Used for checking for new day


    for counter in itercount():
        # Sleep at the end of every loop
        missing = tw.sleep(polling_rate)
        # Loop again to avoid edge case where the machine wakes up and is immediately put back to sleep
        while missing > 2 and missing > polling_rate / 10:
            missing = tw.sleep(polling_rate)
        polling_rate = UA.polling_rate * 60

        # Check for a new day
        if time.localtime().tm_yday != cur_day:
            tw.reset()
            cur_day = time.localtime().tm_yday
            print(time.strftime('\n\nToday is %A, %-m-%d'), '\n' + '#' * 80)
            if verbose >= 2:
                print("Elapsed", fmt_time(tw.elapsed))
                for proc in schedule_apps:
                    proc.print()
                    print('\n')


        # Read the schedule file if it's been updated
        if os.path.getmtime(UA.schedule) > last_schedule_read:
            if last_schedule_read:
                aprint("Schedule file updated:", '\n' + '#' * 80)
            else:
                # The first run
                print("\n\nSchedule file:", '\n' + '#' * 80)
            last_schedule_read = time.time()
            schedule_apps = read_schedule(schedule_apps, msgbox if counter else warn)

        # Run scripts
        for proc in schedule_apps:
            if UA.stagger and (time.time() - last_run) / 60 < UA.stagger:
                break
            if proc.ready(tw, polling_rate):
                proc.run(testing_mode=UA.testing)
                last_run = time.time()


        # Put the computer to sleep after checking to make sure nothing is going on.
        if idle_sleep and tw.idle > idle_sleep:
            if shared.COMP.plugged_in():
                # Plugged mode waits for idle system.
                ready, results = tman.query(is_busy, max_age=polling_rate * 1.5)
                if ready and not results:
                    print("Going to sleep\n")
                    if not UA.testing:
                        tw.sleepy_time()
                        polling_rate = 2
            else:
                # Battery Mode doesn't wait for idle system.
                print("Idle and unplugged. Going to sleep.\n")
                if not UA.testing:
                    tw.sleepy_time()
                    polling_rate = 2


if __name__ == "__main__":
    UA = parse_args()
    if UA.idle:
        check_install('iostat', 'sar',
                      msg='''sudo apt install sysstat sar
                      --idle requires iostat () to determine if the computer can be put to sleep.''')
    # Min level to print messages:
    shared.VERBOSE = UA.verbose
    shared.LOG_DIR = UA.logs
    mkdir(UA.logs)
    gohome()
    os.nice(shared.NICE)
    print("Log started at:", local_time(shared.START_TIME), '=', int(shared.START_TIME))
    main(shared.VERBOSE)
