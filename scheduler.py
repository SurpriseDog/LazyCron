#!/usr/bin/python3

import os
import re
import time
import shutil
import bisect
import random
import datetime
import subprocess
from datetime import datetime as dada

import shared
import sd.chronology as chronos

from shared import aprint
from timewatch import get_idle

from sd.msgbox import msgbox
from sd.columns import indenter
from sd.common import safe_filename, error, check_internet, spawn, crop, quickrun
from sd.common import search_list, DotDict, warn, unique_filename, ConvertDataSize, rfs


def get_day(day, cycle, today=None):
    "Given a day of the week/month/year, return the next occurence"
    if not today:
        today = dada(*dada.now().timetuple()[:3])
    if cycle == 'week':
        delta = datetime.timedelta((day - today.weekday()))
        if delta.days < 0:
            delta += datetime.timedelta(7)
    elif cycle == 'month':
        delta = datetime.timedelta((day - today.day))
        if delta.days < 0:
            delta = chronos.add_date(today, months=1).replace(day=day) - today
    elif cycle == 'year':
        month, day = day
        date = today.replace(month=month, day=day)
        if date < today:
            date = date.replace(year=date.year)
        return date
    else:
        error('cycle', cycle, "unsupported")
    return today + delta


def run_proc(cmd, log, nice=None):
    "Spawn a thread to run a command and then write to log if needed."

    if nice:
        nice -= shared.NICE
        os.nice(nice)

    folder, file = os.path.split(log)
    log = os.path.join(folder, safe_filename(file))

    ofilename = unique_filename(log+'.log')
    efilename = unique_filename(log+'.err')

    ofile = open(ofilename, mode='w')
    efile = open(efilename, mode='w')

    ret = subprocess.run(cmd, check=False, stdout=ofile, stderr=efile, shell=True)
    code = ret.returncode

    oflag = bool(ofile.tell())
    eflag = bool(efile.tell())
    ofile.close()
    efile.close()


    # Remove file if nothing was written to them
    if not oflag:
        os.remove(ofilename)
    if not eflag:
        os.remove(efilename)

    if code:
        print()
        warn(cmd, "\nReturned code", code)
        print("Errors in:", efilename)


        # msgbox(cmd, "returned code", str(code), '\n', 'Errors in', efilename)
        # Does not work because run_proc started in a thread

        quickrun('sd/msgbox.py', ' '.join((crop(cmd), "returned code", str(code))))


TIME_REQS = ('idle', 'busy', 'random', 'elapsed')
DATA_REQS = ('disk', 'network')

def get_reqs():
    "Requirements to run processes"
    # These are default values if no argument given by user
    reqs = DotDict(plugged=True,
                   unplugged=True,
                   idle=10 * 60,
                   busy=10 * 60,
                   closed=True,
                   open=True,
                   random=86400,
                   start=1,
                   online=True,
                   elapsed=10 * 60,
                   skip=1,
                   max=0,
                   reps=1,
                   nice=5,
                   disk=shared.LOW_DISK,
                   network=shared.LOW_NET,
                   cpu=shared.LOW_CPU,
                  )

    aliases = dict(plug='plugged',
                   unplug='unplugged',
                   lazy='idle',
                   rand='random',
                   startup='start',
                   shut='closed',
                   skipped='skip',
                   internet='online',
                   used='elapsed',
                   usage='elapsed',
                   maximum='max',
                   disc='disk',
                   repititions='reps',
                   repetitions='reps',
                   )
    assert not set(aliases.keys()) & set(reqs.keys())             # No repeats between aliases and real reqs
    assert all([val in reqs.keys() for val in aliases.values()])  # All values in aliases are legit reqs
    return reqs, aliases


class App:
    "Spawn processes during windows of time when certain conditions are met"

    def __init__(self, args):
        "Defaults:"
        self.window = []            # Start and stop times
        self.date_window = []       # Allowed days
        self.start = 0              # Start time in UTC
        self.stop = 0               # End time in UTC
        self.freq = None            # Frequency. None = Run once a day
        self.history = []           # When the app last ran

        self.last_run = 0           # Last time the script was run
        self.next_run = 0           # Next time the script can run

        self.args = args            # Preserve initial setup args
        self.path = args['path']    # Path to script
        self.thread = None          # Thread starting running process
        self.verbose = shared.VERBOSE

        name = list(indenter(os.path.basename(self.path), wrap=64))
        if len(name) > 1:
            self.name = name[0].rstrip(',') + '...'
        else:
            self.name = name[0].rstrip(',')

        self.reqs, self.aliases = get_reqs()        # Requirements and aliases to requirements
        self.process_args()                         # Process data lines
        self.calc_window()


    def process_reqs(self, args):
        "Process requirements field"
        # print("processing requirements field:", args)
        found = []

        inversions = dict(unplugged='plugged', open='closed')

        for arg in args:
            split = arg.lower().strip().split()
            arg = split[0]
            val = (' '.join(split[1:])).strip()
            match = search_list(arg, self.reqs.keys(), get='first')
            if not match:
                match = search_list(arg, self.aliases.keys(), get='only')
                if match:
                    match = self.aliases[match]
            if not match:
                error("Can't find requirement:", arg)

            # Get default value if not supplied
            if not val:
                val = self.reqs[match]
            # print("Processing req:", match, repr(val))


            # deal with plugged/unplugged closed/open...
            if match in inversions:
                match = inversions[match]
                inverted = True
            else:
                inverted = False

            # Non numeric conversions
            if match in TIME_REQS:
                val = chronos.convert_user_time(val, default='minutes')
            elif match in ('plugged', 'closed', 'online'):
                val = bool(val)
            elif match in DATA_REQS:
                val = re.sub('second[s]*', 's', val)
                val = re.sub('[/\\\\]*[s]$', '', val)
                val = ConvertDataSize()(val)
            else:
                val = int(val)

            if inverted:
                val = not val


            found.append(match)
            self.reqs[match] = val

        # Delete reqs that were not specified by user
        for key in list(self.reqs.keys()):
            if key not in found:
                del self.reqs[key]


    def verify(self,):
        "Check to make sure it can be run"
        def alert(*args):
            warn(*args)
            msgbox(*args)
            return False

        path = self.path.split()[0]
        if path != 'msgbox' and not path.startswith('#'):
            if not shutil.which(path):
                return alert("Path does not exist:", path)

        return True


    def process_time(self, section):
        vals = chronos.convert_ut_range(section, default='hours')
        if len(vals) == 2:
            self.window.append([vals[0], vals[1]])
        else:
            error("Can't read time:", section)


    def process_date(self, section):
        try:
            days, cycles = list(zip(*map(chronos.udate, re.split('-| to ', section))))
        except ValueError:
            error("Cannot understand text:", section)
        if len(set(cycles)) != 1:
            error("Cycle length in", section, "must be the same")
        cycles = cycles[0]
        start = days[0]
        if len(days) == 1:
            end = start
        else:
            end = days[1]
        self.date_window.append((start, end, cycles))


    def process_args(self):
        args = self.args
        for key, values in args.items():
            values = str(values)

            # Handle star values
            if values == '*':
                if key == 'reqs':
                    self.reqs = DotDict()
                elif key == 'time':
                    self.window = [[0, 86400]]
                continue

            else:
                values = values.split(',')
                if key == 'reqs':
                    self.process_reqs(values)
                else:
                    for val in values:
                        if key == 'time':
                            self.process_time(val)
                        if key == 'date':
                            self.process_date(val)
                        if key == 'frequency':
                            self.freq = chronos.convert_user_time(val, default='minutes')


    def __str__(self):
        return str({key: val for key, val in self.__dict__.items() if key != 'args'})


    def __repr__(self):
        return self.name


    def print(self):
        "Print a detailed representation of each app"

        print('Name: ', self.name)
        if self.window or self.date_window:
            now = time.time()
            print('Start:', chronos.local_time(self.start, '%a %m-%d %I:%M %p'), '=',
                  chronos.fmt_time(self.start - now))

            # Make it so that if the user says it ends on a certain day, that's what the text says
            # Example: Thu-Mon used to say it started Thursday and ended on Tuesday at Midnight.
            # Now it says Monday at 11:59PM - A minor inaccuracy for the sake of readability
            stop = self.stop
            if dada.fromtimestamp(stop).strftime('%H%M%S') == '000000':
                stop -= 1
            print('Stop: ', chronos.local_time(stop, '%a %m-%d %I:%M %p'), '=',
                  chronos.fmt_time(self.stop - now))
        if self.freq:
            print('Freq: ', chronos.fmt_time(self.freq))
        elif self.freq is None:
            print('Freq: ', '*')

        print('Path: ', self.path)

        # Print reqs
        out = {}
        for key, val in sorted(self.reqs.items()):
            if key in DATA_REQS:
                val = rfs(val) + '/s'
            if key in TIME_REQS and val >= 300:
                val = chronos.fmt_time(val)
            out[key] = val
        print('Reqs: ', out)


        print('in_window:', self.in_window())
        if self.next_run:
            print('Next_run:', chronos.local_time(self.next_run))


    def running(self):
        "Check if process is already running."
        if self.thread and self.thread.is_alive():
            return True
        return False
        # Search system wide
        # return ps_running(self.path)


    def calc_date(self, extra=0):
        "Get seconds until next date when allowed to run"
        inf = float("inf")
        new_start = inf
        new_stop = 0
        today = dada(*dada.now().timetuple()[:3]) + datetime.timedelta(days=extra)

        # For start date, end date, cycle type in date window
        for sd, ed, cycle in self.date_window:
            if cycle == 'year':
                # If today is after end date, advance time one year
                if today > ed:
                    sd = sd.replace(year=sd.year+1)     # Start Date
                    ed = ed.replace(year=ed.year+1)     # End Date
                start = sd.timestamp()
                stop = ed.timestamp()
            else:
                stop = get_day(ed, cycle, today=today)
                start = get_day(sd, cycle, today=today)

                # Move start date back one cycle if after end date
                if start > stop:
                    if cycle == 'week':
                        start = chronos.add_date(start, days=-7)
                    elif cycle == 'month':
                        start = chronos.add_date(start, months=-1)
                    else:
                        raise ValueError("Unkown cycle length:", cycle)
                # print('calc_date', cycle, sd, ed, start, stop,  self.name)

                # Convert to timestamps
                stop = stop.timestamp()
                start = start.timestamp()


            if start < new_start:
                new_start = start
                new_stop = stop
        return new_start, new_stop


    def calc_window(self):
        "Calculate the next start and stop window for the proc in unix time"
        inf = float("inf")
        now = time.time()
        midnight = round(now - chronos.seconds_since_midnight())
        if self.date_window:
            self.start, self.stop = self.calc_date()
        else:
            self.start = midnight
            self.stop = midnight

        def get_first():
            "Find earliest start, return True if updated."
            new_start = inf
            for start, stop in self.window:
                if stop < start:
                    stop += 86400
                start += self.start
                stop += self.stop
                if start < new_start and stop > now:
                    new_start = start
                    new_stop = stop
            if new_start < inf:
                self.start = new_start
                self.stop = new_stop
                return True
            return False

        if self.window:
            if not get_first():
                # If the stop time is in the past, shift time forward and calculate again.
                if not self.date_window:
                    self.start += 86400
                    self.stop += 86400
                else:
                    self.start, self.stop = self.calc_date(extra=1)
                get_first()
        else:
            self.stop += 86400

        if self.history and (self.window or self.date_window):
            if self.start > now:
                print("Next run in", chronos.fmt_time(self.start - now), 'for', self.name)
            else:
                print("Time window for", self.name, 'closes in', chronos.fmt_time(self.stop - now))

        if not now <= self.stop:
            error('Miscalculation!', self.name, now, 'start', self.start, 'stop', self.stop)


    def in_window(self):
        "Check if within time window to run, otherwise recalculate a new time window"
        now = time.time()
        if now < self.start:
            return False
        if self.start <= now <= self.stop:
            '''
            next_run now set by run command
            if self.freq is not None:           # The *
                if self.start <= self.last_run <= self.stop:
                    # aprint("Already ran in this window")
                    return False
            return True
            '''
            return True
        else:
            # Recalculate
            self.calc_window()
            return self.in_window()


    def show_history(self,):
        "Show the history of timestamps for process"
        # Compact way to show time start. Numbers indicate seconds since program start
        history = [str(int(ts - shared.START_TIME)) for ts in self.history[-11:]]

        if len(history) >= 2:
            if len(history) < 11:
                print(', '.join(history))
            else:
                print('...' + ', '.join(history[-10:]))

    def alert(self, *args, v=3):
        "Show time, process name and message"
        if self.verbose >= v:
            args = [int(item) if type(item) == float else item for item in args]
            aprint(*args, '::', self.name, )


    def ready(self, tw, polling_rate, busy):
        "Is the process ready to be run?"
        now = time.time()

        # Check if process is already running.
        if self.thread and self.thread.is_alive():
            self.alert("Still running!")
            return False

        if self.window or self.date_window:
            if not self.in_window():
                self.alert("Outside of window starting at", chronos.local_time(self.start))
                return False

        if self.next_run and now < self.next_run:
            self.alert("Next run at", chronos.local_time(self.next_run))
            return False

        # Check App requirements.
        # Not a match statement. No increase in speed and breaks compatability with python versions < 3.10
        # Future maybe put if verbose > ? before each alert statement for optimization, but probably not needed
        if self.reqs:

            # Usage requirements:
            if 'idle' in self.reqs:
                if tw.idle < self.reqs.idle or get_idle() < self.reqs.idle:
                    self.alert("Idle time not reached")
                    return False
            if 'busy' in self.reqs and tw.idle > self.reqs.busy:
                self.alert("Idle for too long:", tw.idle, '>', self.reqs.busy)
                return False
            if 'random' in self.reqs and random.random() > polling_rate / self.reqs.random:
                # Random value not reached
                self.alert("Random value not reached: 1 in", int(1 / (polling_rate / self.reqs.random)))
                return False
            if 'elapsed' in self.reqs and tw.today_elapsed < self.reqs.elapsed:
                self.alert("Elapsed not reached", tw.today_elapsed, '<', self.reqs.elapsed)
                return False

            # History requirements:
            if 'start' in self.reqs and len(self.history) >= self.reqs.start:
                return False
            if 'max' in self.reqs and len(self.history) >= self.reqs.max:
                self.alert("Max number of times reached")
                return False
            if 'reps' in self.reqs:

                # Start time if in window, otherwise midnight:
                start = self.start if self.start else now - chronos.seconds_since_midnight()
                count = len(self.history) - bisect.bisect_left(self.history, start)

                # Fixed bug where skipped runs counted towards reps
                if 'skip' in self.reqs:
                    count -= self.reqs.skip

                if count >= self.reqs.reps:
                    self.alert("Max number of reps reached:", count, 'since', chronos.local_time(start))
                    return False

            # Machine requirements:
            for name, func in [('cpu', busy.get_cpu), ('disk', busy.get_disk), ('network', busy.get_net)]:
                if name in self.reqs:
                    val = func()
                    if val is None:
                        # None value = thread not ready yet
                        return False
                    if val >= self.reqs[name]:
                        self.alert(name, "usage too high to continue")
                        return False

            # State requirements:
            if 'closed' in self.reqs and self.reqs.closed == shared.COMP.lid_open():
                self.alert("Wrong lid state")
                return False
            if 'plugged' in self.reqs and self.reqs.plugged != shared.COMP.plugged_in():
                self.alert("Wrong plug state")
                return False
            if 'online' in self.reqs and not check_internet():
                self.alert("Not Online")
                return False

        return True


    def run(self, testing_mode):
        "Run the process in seperate thread while writing output to log."
        now = time.time()

        self.history.append(now)
        self.last_run = now

        # If no frequency was specifed, then it will run every day. Note! 0 != None
        if self.freq is None:
            # Set to midnight
            self.next_run = now + 86400 - chronos.seconds_since_midnight()
        elif self.freq:
            # Otherwise add freq
            self.next_run = now + self.freq


        # Must be in run to trigger self.next_run
        if 'skip' in self.reqs and len(self.history) <= self.reqs.skip:
            self.alert("Skip", len(self.history), 'of', self.reqs.skip, v=2)
            return

        if self.path.lstrip().startswith('#'):
            testing_mode = True
        if testing_mode:
            text = "Did not start process"
        else:
            text = "Started process"
            if self.path.startswith('msgbox '):
                msg = re.sub('^msgbox ', '', self.path).strip().strip('"').strip("'")
                msgbox(msg)
                self.thread = None
            else:
                nice = 5 if 'nice' not in self.reqs else self.reqs.nice
                filename = safe_filename(self.name + '.' + str(int(now)))
                log_file = os.path.abspath(os.path.join(shared.LOG_DIR, filename))
                _, self.thread = spawn(run_proc, self.path, log=log_file, nice=nice)

        self.alert(text, v=1)
        if self.verbose >= 2:
            self.show_history()
