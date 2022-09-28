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
import scheduler

from shared import aprint
from timewatch import TimeWatch
from how_busy import Busy
from sd.chronology import convert_user_time, fmt_time

from sd.msgbox import msgbox
from sd.columns import auto_cols
from sd.easy_args import easy_parse
from sd.common import itercount, gohome, check_install, rfs, mkdir, warn, spawn, search_list, DotDict



def parse_args():
    "Parse arguments"

    positionals = [\
    ["schedule", '', str, 'schedule.txt'],
    "Filename to read schedule from."
    ]

    args = [\
    ['polling', 'polling', str, '1'],
    "How often to check (minutes)",
    ['idle', '', str],
    "How long to wait before going to sleep (minutes)",
    ['verbose', '', int, 1],
    "What messages to print",
    ['testing', '', bool],
    "Do everything, but actually run the scripts.",
    ['logs', '', str, '/tmp/LazyCron_logs'],
    ['reqs', '', str],
    '''
    Apply requirements to all processes (will not override existing reqs)
    Example: --reqs 'nice 10,  cpu 10'
    ''',
    ['skip', '', int, 0],
    "Don't run apps on startup, wait <x> minutes",
    ['stagger', '', float, 0],
    "Wait x minutes between starting programs.",
    ]

    hidden = [\
    ['debug', '', bool],
    ]

    args = easy_parse(args,
                      positionals,
                      hidden=hidden,
                      usage='<schedule file>, --options...',
                      description='Monitor the system for idle states and run scripts at the best time.')


    cut = lambda x: convert_user_time(x, default='minutes')
    args.idle = cut(args.idle)
    args.polling = cut(args.polling)

    # Defaults if no value given
    if args.skip is None:
        args.skip = 8
    if args.verbose is None:
        args.verbose = 2

    return DotDict(vars(args))


def is_busy(busy,):
    "Return True if disk or network usage above defaults"
    def fmt(num):
        return rfs(num)+'/s'

    # Values are cached by Busy class.
    # Requesting them spins up a thread to check their values, but returns None if not ready yet.
    net_usage = busy.get_net()
    disk_usage = busy.get_disk()
    cpu_usage = busy.get_cpu()
    if None in (net_usage, disk_usage, cpu_usage):
        # Value not set yet
        return True


    # Network Usage
    if net_usage >= shared.LOW_NET:
        aprint("Busy: Network Usage:", fmt(net_usage))
        return True

    # Disk Usage
    if disk_usage >= shared.LOW_DISK:
        aprint("Busy: Disk usage:", fmt(disk_usage))
        return True

    # Cpu usage
    if cpu_usage >= shared.LOW_CPU:
        aprint("Busy: Cpu Usage:", fmt(cpu_usage))
        return True

    aprint("Not Busy - Network Usage:", fmt(net_usage), "Disk usage:", fmt(disk_usage))
    return False


def read_line(line, warn_score=5):
    "Given a line delimited by tabs and spaces, convert it to 5 fields"

    candidates = []
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
            cols = read_line(line)
            if not cols:
                alert("Can't process line:", repr(line), "\nMake sure you put tabs in between columns")
                continue
            line = dict(zip(headers, cols))


            # See if it matches an existing App
            for proc in schedule_apps:
                if line == proc.args:
                    print("Using existing App definition:", proc.name)
                    new_sched.append(proc)
                    break

            # Otherwise try to create a new one
            else:
                # Show the args used to creat proc
                auto_cols([[item.title()+':' for item in headers], [repr(item) for item in cols], []])

                # Slip in command line reqs:
                if UA.reqs:
                    reqs = line['reqs'].strip()
                    if reqs == '*':
                        reqs = UA.reqs.strip()
                    else:
                        if reqs and not reqs.endswith(','):
                            reqs += ', '
                        reqs += UA.reqs.strip()
                        print(reqs)
                        line['reqs'] = reqs

                # Try to process each line
                try:
                    proc = scheduler.App(line)

                # Bare exception to cover any processing errors
                except Exception as e:      # pylint: disable=broad-except
                    alert("Could not process line:", line)
                    traceback.print_exc()
                    print(e, '\n\n\n')
                    continue
                    # proc.add_reqs(UA.reqs)
                proc.print()
                print('\n'*2)

                if proc.cmd:
                    new_sched.append(proc)


    # Modify in place
    if new_sched:
        schedule_apps[:] = new_sched



class Debugger:
    "Hidden debug tool - Read user input and print status while running"

    def __init__(self, twatch, schedule_apps):
        self.twatch = twatch
        self.schedule_apps = schedule_apps


    def print_procs(self,):
        for proc in self.schedule_apps:
            proc.print()
            print('\n')


    def find_app(self, name):
        apps = {app.name:app for app in self.schedule_apps}
        match = search_list(name, apps, get='all')
        if len(match) == 1:
            return match[0]
        else:
            print('Found', len(match), 'matches for', name)
            _ = [print(m.name) for m in match]
            return None


    def loop(self,):
        history = []
        while True:
            cmd = input().lower().strip()
            if not cmd:
                continue

            # Rerun previous commands with up arrows
            up = cmd.count('\x1b[a') - cmd.count('\x1b[b')
            if up and len(history) >= up > 0:
                cmd = history[-up]
                print(cmd)
            else:
                history.append(cmd)

            self.process(cmd)

    def process(self, cmd):
        "Process a user typed command"
        first = cmd.split()[0]
        tail = cmd[len(first)+1:]

        if cmd == 'time':
            self.twatch.status()

        elif cmd == 'all':
            self.print_procs()

        elif first == 'vars':
            match = self.find_app(tail)
            if match:
                print(match)

        elif first == 'reqs':
            match = self.find_app(tail)
            if match:
                match.reqs.print()

        elif first == 'print':
            # Print the app given after app
            match = self.find_app(tail)
            if match:
                match.print()

        elif first in ('run', 'start'):
            match = self.find_app(tail)
            if match:
                match.run(self.twatch, False)

        elif cmd == 'args':
            print(UA)

        # Changing verbose requires special handling
        elif first == 'verbose':
            try:
                val = int(tail)
            except ValueError:
                return
            shared.VERBOSE = val
            for app in self.schedule_apps:
                app.verbose = val

        # Change other user arguments
        elif first in UA:
            try:
                val = cmd.split()[1]
            except IndexError:
                return
            try:
                val = int(val)
            except ValueError:
                return
            UA[first] = int(val)
            print(UA)

        else:
            print(cmd, '???')
        print()



def main(verbose=1):
    polling_rate = 0                        # Time to rest at the end of every loop
    idle_sleep = UA.idle                    # Go to sleep after this long plugged in
    twatch = TimeWatch(verbose=verbose)
    last_schedule_read = 0                  # last time the schedule file was read
    last_run = 0                            # Time when the last program was started
    schedule_apps = []                      # Apps found in schedule.txt
    cur_day = time.localtime().tm_yday      # Used for checking for new day
    busy = Busy(expiration=max(UA.polling * 2.5, 60))


    if UA.debug:
        spawn(Debugger(twatch, schedule_apps).loop)

    for counter in itercount():
        # Sleep at the end of every loop
        missing = twatch.sleep(polling_rate)
        # Loop again to avoid edge case where the machine wakes up and is immediately put back to sleep
        while missing > 2 and missing > polling_rate / 10:
            missing = twatch.sleep(polling_rate)
        polling_rate = UA.polling

        # Check for a new day
        if time.localtime().tm_yday != cur_day:
            twatch.reset()
            cur_day = time.localtime().tm_yday
            print(time.strftime('\n\n\nToday is %A, %-m-%d'), '\n' + '#' * 80)
            scheduler.compress_logs(shared.LOG_DIR)


        # Read the schedule file if it's been updated
        if os.path.getmtime(UA.schedule) > last_schedule_read:
            if last_schedule_read:
                aprint("Schedule file updated:", '\n' + '#' * 80)
            else:
                # The first run
                print("\n\nSchedule file:", '\n' + '#' * 80)
            last_schedule_read = time.time()
            read_schedule(schedule_apps, msgbox if counter else warn)

        # Run scripts
        for proc in schedule_apps:
            if UA.stagger and (time.time() - last_run) / 60 < UA.stagger:
                break
            if proc.ready(twatch, polling_rate, busy):
                if UA.skip and time.time() - shared.START_TIME < UA.skip * 60:
                    proc.run(twatch, testing_mode=UA.testing, skip_mode=True)
                else:
                    proc.run(twatch, testing_mode=UA.testing, skip_mode=False)
                    last_run = time.time()


        # Put the computer to sleep after checking to make sure nothing is going on.
        if idle_sleep and twatch.idle > idle_sleep:
            if shared.COMP.plugged_in():
                # Plugged mode waits for idle system.
                if not is_busy(busy):
                    aprint("Going to sleep:    (ᵕ≀ ̠ᵕ )......zzzzzzzZZZZZZZZ")
                    slept_for = twatch.sleepy_time()
                    if slept_for > 4:
                        print('\n\n\n')
                        aprint("Waking up after", fmt_time(slept_for))
                        polling_rate = 2
                    else:
                        print("Sleep command failed!")



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
    print(time.strftime('Log started on %A, %-m-%d at %H:%M'), '=', int(shared.START_TIME))
    main(shared.VERBOSE)
