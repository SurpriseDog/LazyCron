#!/usr/bin/python3
# LazyCron - "Your computer will get around to it eventually."
# Usage: Run with -h for help.

################################################################################

import os
import re
import time
import traceback
import importlib
import multiprocessing as mp

import shutil
import shared
import timewatch
import scheduler
from shared import aprint
from lc_debugger import Debugger

from sd.msgbox import msgbox
from sd.columns import auto_cols
from sd.easy_args import easy_parse
from sd.cut import convert_user_time
from sd.format_number import fmt_time
from sd.common import itercount, gohome, rfs, mkdir, warn, spawn, DotDict, sig


# Choose which functions to import based on what's available:
if importlib.util.find_spec("psutil"):
    import how_busy_psutil as how_busy
else:
    import how_busy_linux as how_busy       # Returns 0 if system utility not available
    if shared.PLATFORM == 'linux':
        print("psutil not available... using linux system utilities.")
    else:
        print("Please install psutil to get system monitoring.")


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
    "How long to wait before going to sleep while plugged in.",
    ['idlebatt', '', str],
    "How long to wait before going to sleep on battery power.",
    ['verbose', '', int, 1],
    "What messages to print",
    ['testing', '', bool],
    "Do everything, but actually run the scripts.",
    ['logs', '', str, '/tmp/LazyCron_logs'],
    "What folder to put the log files in.",
    ['nice', '', int, 4],
    '''Base nice level to spawn processes with.
    Higher numbers up to 20 = less demanding of cpu time.
    (linux only)
    ''',
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


    cut = lambda x: convert_user_time(x, default='minutes') if x else None
    args.idle = cut(args.idle)
    args.idlebatt = cut(args.idlebatt)
    args.polling = cut(args.polling)

    # Defaults if no value given
    if args.skip is None:
        args.skip = 8
    if args.verbose is None:
        args.verbose = 2

    return DotDict(vars(args))


class Busy:
    "Poll the system to see if system is busy, returns None if value not ready yet"
    def __init__(self, expiration=100):
        self.expiration = expiration        # How long to keep values before querying again
        self.net = DotDict(que=None, thread=None, timestamp=0, value=None,)
        self.disk = DotDict(que=None, thread=None, timestamp=0, value=None,)
        self.cpu = DotDict(que=None, thread=None, timestamp=0, value=None,)

    def get_net(self, *args, **kargs):
        return self._query(self.net, how_busy.get_network_usage, *args, **kargs)

    def get_disk(self, *args, **kargs):
        return self._query(self.disk, how_busy.all_disk_usage, *args, **kargs)

    def get_cpu(self, *args, **kargs):
        return self._query(self.cpu, how_busy.get_cpu_usage, *args, **kargs)


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
        aprint("Busy: Cpu Usage:", sig(3.14*10, 2) + '%')
        return True

    aprint("Not Busy - Network Usage:", fmt(net_usage), "Disk usage:", fmt(disk_usage))
    return False


def is_idle(twatch,):
    "Is the computer idle?"
    if UA.idle and twatch.idle > UA.idle and shared.COMP.plugged_in():
        return True
    if UA.idlebatt and twatch.idle > UA.idlebatt and not shared.COMP.plugged_in():
        return True
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



def go2sleep(twatch):
    "Look for missing time indicating sleep"
    aprint("Going to sleep:    (ᵕ≀ ̠ᵕ )......zzzzzzzZZZZZZZZ")
    cur_day = time.localtime().tm_yday
    if twatch.sleepy_time():
        start = time.time()
        for x in range(20):
            time.sleep(1)
            if time.time() - start > x * 1.2 + 2:
                slept_for = time.time() - start - x
                break
        else:
            slept_for = 0

        if slept_for > 4:
            print('\n\n')
            if time.localtime().tm_yday == cur_day:
                aprint("Waking up after", fmt_time(slept_for))
            return True
    print("Sleep command failed!")
    return False


class ScriptManager:
    "Keep track of all the available scripts and when last run"

    def __init__(self, busy, twatch, file):
        self.schedule_apps = []                     # Apps found in schedule.txt
        self.schedule_file = file                   # Schedule File Name
        self.last_schedule_read = 0                 # Last time the schedule file was read
        self.last_run = 0                           # Time when the last program was started
        self.busy = busy
        self.twatch = twatch
        self.alert = msgbox                         # Set function to send alerts

        self.sleep_procs = []                       # List of procs ran on suspend
        self.sleep_check = 0                        # Last time sleepy_time was called


    def update(self,):
        "Check schedule file and update if new"
        if os.path.getmtime(self.schedule_file) > self.last_schedule_read:
            if self.last_schedule_read:
                aprint("Schedule file updated:", '\n' + '#' * 80)
            else:
                # The first run
                print("\n\nSchedule file:", '\n' + '#' * 80)
            self.last_schedule_read = time.time()
            self.read_schedule()


    def sleepy_time(self, polling_rate):
        "Run scripts with sleep flag, return True if ready to sleep"
        now = time.time()
        ret = False

        if self.sleep_check and now - self.sleep_check >= polling_rate * 10:
            # If there is too much time between sleepy_time calls then reset.
            self.sleep_procs = []
            self.sleep_check = 0

        # From previous run
        if self.sleep_procs:
            # If too much time has elapsed
            if now - self.sleep_check > 600:
                ret = True
            else:
                # Go through each sleep proc and see if done
                for proc in self.sleep_procs:
                    if proc.running():
                        break
                else:
                    ret = True

        # New run
        else:
            procs = self.run_scripts(polling_rate, flag='suspend')
            if not procs:
                ret = True
            else:
                self.sleep_procs = procs
                self.sleep_check = now


        # Return True if ready to sleep
        if ret:
            self.sleep_procs = []
            self.sleep_check = 0
            return True
        else:
            return False


    def run_scripts(self, polling_rate, flag=None):
        "Attempt to run all of the scripts in schedule"

        started = []
        for proc in self.schedule_apps:
            if UA.stagger and (time.time() - self.last_run) / 60 < UA.stagger:
                break

            if proc.ready(self.twatch) and proc.check_reqs(self.twatch, polling_rate, self.busy, flag=flag):

                if UA.skip and time.time() - shared.START_TIME < UA.skip * 60 and 'start' not in proc.reqs.reqs:
                    result = proc.run(self.twatch, testing_mode=UA.testing, skip_mode=True,)
                else:
                    result = proc.run(self.twatch, testing_mode=UA.testing, skip_mode=False,)

                if result:
                    started.append(proc)
                    self.last_run = time.time()
        return started




    def read_schedule(self,):
        "Read the schedule file"

        new_sched = []
        headers = "time frequency date reqs path".split()

        with open(self.schedule_file) as f:
            for line in f.readlines():
                # Ignore comments and empty lines
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                # Find lines that have 5 fields in them
                cols = read_line(line)
                if not cols:
                    self.alert("Can't process line:", repr(line), "\nMake sure you put tabs in between columns")
                    continue
                line = dict(zip(headers, cols))


                # See if it matches an existing App
                for proc in self.schedule_apps:
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
                        self.alert("Could not process line:", line)
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
            self.schedule_apps[:] = new_sched


def mp_start(target, args=None, kwargs=None, daemon=True):
    '''Start a seperate process for a function with multiprocessing
    args = list of args
    kwargs = dict of keyword args
    daemon = subprocess is automatically terminated after the parent process ends to prevent orphan processes.
    '''
    proc = mp.Process(target=target, args=args, kwargs=kwargs)
    proc.daemon = daemon
    proc.start()
    return proc


def main(verbose=1):
    polling_rate = 0                        # Time to rest at the end of every loop
    twatch = timewatch.TimeWatch(verbose=verbose)

    cur_day = time.localtime().tm_yday      # Used for checking for new day
    sleep_failed = 0                        # Number of times Sleep command failed.
    just_slept = False                      # Just woke up from sleep

    busy = Busy(expiration=max(UA.polling * 2.5, 60))
    sman = ScriptManager(busy, twatch, UA.schedule)     # Script Manager


    if UA.debug:
        spawn(Debugger(twatch, sman.schedule_apps, UA).loop)

    for counter in itercount():
        if counter == 1:
            sman.alert = warn

        # Sleep at the end of every loop
        missing = twatch.sleep(polling_rate)
        # Loop again to avoid edge case where the machine wakes up and is immediately put back to sleep
        while missing > 2 and missing > polling_rate / 10:
            if not just_slept:
                just_slept = True
            missing = twatch.sleep(polling_rate)
        polling_rate = UA.polling

        # Check for a new day
        if time.localtime().tm_yday != cur_day:
            twatch.reset()
            cur_day = time.localtime().tm_yday
            print(time.strftime('\n\n\nToday is %A, %-m-%d'), '\n' + '#' * 80)
            mp_start(scheduler.compress_logs, args=(shared.LOG_DIR,))
            sleep_failed = 0


        if just_slept:
            sman.run_scripts(polling_rate, flag='wake')
            just_slept = False
            continue                        # Allows the computer to restablish wifi after sleep


        sman.update()                       # Update schedule file if it's been updated
        sman.run_scripts(polling_rate)      # Run the scripts

        # Give up after sleep command fails too much, (messes up time calculations)
        if sleep_failed <= 3:
            # Put the computer to sleep after checking to make sure nothing is going on.
            if is_idle(twatch) and not is_busy(busy):
                # Run any sleep scripts:
                if sman.sleepy_time(polling_rate) and go2sleep(twatch):
                    polling_rate = 2
                    just_slept = True
                else:
                    sleep_failed += 1




if __name__ == "__main__":
    UA = parse_args()
    timewatch.verify()
    os.nice(UA.nice)                # Script level nice value, spawned processes can be higher
    shared.VERBOSE = UA.verbose     # Min level to print messages:
    shared.LOG_DIR = UA.logs
    mkdir(UA.logs)
    gohome()
    print(time.strftime('Log started on %A, %-m-%d at %H:%M'), '=', int(shared.START_TIME))
    main(shared.VERBOSE)
