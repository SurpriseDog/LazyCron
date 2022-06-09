#!/usr/bin/python3

import os
import re
import time
import random
import datetime
import subprocess
from datetime import datetime as dada

import shared
import computer
import sd.chronology as chronos

from shared import aprint
from sd.msgbox import msgbox
from sd.columns import indenter

from sd.common import safe_filename, error, read_csv, check_internet, spawn, crop, quickrun
from sd.common import search_list, DotDict, warn, unique_filename


START_TIME = time.time()
COMP = computer.Computer()
LOG_DIR = '/tmp/log_dir'
print("Log started at:", int(START_TIME))


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





def run_proc(cmd, log):
    folder, file = os.path.split(log)
    log = os.path.join(folder, safe_filename(file))

    "Spawn a thread to run a command and then write to log if needed."
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


def read_schedule(schedule_apps, schedule_file, alert=warn):
    '''
    Read the schedule file,
    schedule_apps = List of Apps
    schedule_file = txt file with tab delimted columns
    alert =         send messages to userspace with warn or msgbox
    '''

    new_sched = []
    headers = "time frequency date reqs path".split()
    for line in read_csv(schedule_file, headers=headers, delimiter=("\t", " " * 4), merge=True):
        print('\n\nData =', repr(line))
        if not all(line.values()):
            alert("Empty columns must have a * in them")
            continue
        if len(line) >= 3:
            for proc in schedule_apps:
                if line == proc.args:
                    new_sched.append(proc)
                    break
            else:
                try:
                    proc = App(line)
                except:     # Bare exception to cover any processing errors
                    alert("Could not process line:", line)
                proc.print()
                new_sched.append(proc)
        else:
            alert("Could not process:", '\n'+line)

    # Return the old version if new schedule has errors
    if not new_sched:
        return schedule_apps
    else:
        return new_sched

class App:
    "Spawn processes during windows of time when certain conditions are met"

    def __init__(self, args):
        "Defaults:"
        self.window = []            # Start and stop times
        self.date_window = []       # Allowed days
        self.start = 0              # Start time in UTC
        self.stop = 0               # End time in UTC
        self.freq = 0               # Frequency
        self.history = []           # When the app last ran

        self.last_elapsed = 0       # Last elapsed time at run
        self.last_run = 0           # Last time the script was run
        self.next_elapsed = 0       # Next run time

        self.args = args            # Preserve initial setup args
        self.path = args['path']    # Path to script
        self.thread = None          # Thread starting running process

        name = list(indenter(os.path.basename(self.path), wrap=64))
        if len(name) > 1:
            self.name = name[0].rstrip(',') + '...'
        else:
            self.name = name[0].rstrip(',')

        # Requirements to run process
        self.reqs = DotDict(plugged=False,
                            idle=0,
                            busy=0,
                            closed=False,
                            random=0,
                            start=0,
                            online=0,
                            elapsed=0,
                            )
        self.process_args()         # Process data lines
        self.calc_window()


    def process_time(self, section):
        vals = chronos.convert_ut_range(section, default='hours')
        if len(vals) == 2:
            self.window.append([vals[0], vals[1]])
        else:
            error("Can't read time:", section)

    def process_date(self, section):
        try:
            days, cycles = list(zip(*map(chronos.udate, section.split('-'))))
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

    def process_reqs(self, arg):
        "Process requirements field"
        split = arg.lower().strip().split()
        arg = split[0]
        val = (' '.join(split[1:])).strip()
        if not val:
            val = '10'
        match = search_list(arg, self.reqs.keys(), getfirst=True)
        if not match:
            error("Can't find requirement:", arg)

        if match in ('idle', 'busy', 'random', 'elapsed'):
            self.reqs[match] = chronos.convert_user_time(val)
        else:
            self.reqs[match] = int(val)

    def process_args(self):
        args = self.args
        for key, values in args.items():
            if set(values) == {'*'}:
                continue
            values = values.split(',')
            for val in values:
                if key == 'reqs':
                    if not val:
                        self.reqs = None
                    else:
                        self.process_reqs(val)
                if key == 'time':
                    self.process_time(val)
                if key == 'date':
                    self.process_date(val)
                if key == 'frequency':
                    self.freq = chronos.convert_user_time(val)
                    self.next_elapsed = self.freq


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
            print('Stop: ', chronos.local_time(self.stop, '%a %m-%d %I:%M %p'), '=',
                  chronos.fmt_time(self.stop - now))
        if self.freq:
            print('Freq: ', chronos.fmt_time(self.freq))
        print('Path: ', self.path)
        print('Reqs: ', self.reqs)
        print('in_window:', self.in_window())


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
        for sd, ed, cycle in self.date_window:
            if cycle == 'year':
                if today > ed:
                    sd = sd.replace(year=sd.year+1)     # Start Date
                    ed = ed.replace(year=ed.year+1)     # End Date
                start = sd.timestamp()
                stop = ed.timestamp()
            else:
                stop = get_day(ed, cycle, today=today).timestamp()
                start = stop - (ed - sd) * 86400
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
            self.stop += 86400 - 1  # So it stops just before next day

        if self.history and (self.window or self.date_window):
            if self.start > now:
                print("Next run in", chronos.fmt_time(self.start - now), 'for', self.name)
            else:
                print("Time window for", self.name, 'closes in', chronos.fmt_time(self.stop - now))

        if not now <= self.stop:
            error('miscalculation!', self.name, now, 'start', self.start, 'stop', self.stop)


    def in_window(self):
        "Check if within time window to run, otherwise recalculate a new time window"
        now = time.time()
        if now < self.start:
            return False
        if self.start <= now <= self.stop:
            if not self.freq and self.start <= self.last_run <= self.stop:
                # aprint("Already ran in this window")
                return False
            return True
        else:
            # Recalculate
            self.calc_window()
            return self.in_window()

    def show_history(self,):
        "Show the history of timestamps for process"
        history = self.history
        if len(history) >= 2:
            if len(history) < 10:
                print(', '.join(map(str, history)))
            else:
                print('...' + ', '.join(map(str, history[-10:])))


    def run(self, elapsed, polling_rate, testing_mode, idle=0):
        "Run the process in seperate thread while appending info to log."

        if self.reqs:
            if self.reqs.closed and COMP.lid_open():
                aprint("Lid not closed", v=3)
                return False
            if self.reqs.plugged and not COMP.plugged_in():
                aprint("Not plugged in", v=3)
                return False
            if self.reqs.idle > idle:
                aprint("Idle time not reached", v=3)
                return False
            if self.reqs.busy and idle > self.reqs.busy:
                aprint("Idle for too long:", idle, '>', self.reqs.busy, v=3)
                return False
            if self.reqs.random and random.random() > polling_rate / self.reqs.random:
                # Random value not reached
                return False
            if self.reqs.start and len(self.history) >= self.reqs.start:
                #
                return False
            if self.reqs.elapsed and elapsed < self.reqs.elapsed:
                return False
            if self.reqs.online and not check_internet():
                aprint("Not Online", v=3)
                return False

        if self.running():
            print("\tStill running!")
            return False

        self.last_elapsed = elapsed
        self.last_run = int(time.time())
        self.next_elapsed = elapsed + self.freq

        filename = safe_filename(self.name + '.' + str(int(time.time())))
        log_file = os.path.abspath(os.path.join(LOG_DIR, filename))
        if self.path.lstrip().startswith('#'):
            testing_mode = True
        if testing_mode:
            text = "Did not start process:"
        else:
            # Compact way to record time start. Numbers indicate seconds since program start
            self.history.append(int(time.time()-START_TIME))
            text = "Started process:"
            dirname = os.path.dirname(self.path)
            if not os.path.exists(dirname):
                dirname = None
            if self.path.startswith('msgbox '):
                msg = re.sub('^msgbox ', '', self.path).strip().strip('"').strip("'")
                msgbox(msg)
                self.thread = None
            else:
                _, self.thread = spawn(run_proc, self.path, log=log_file)
        aprint(text, self.name, v=1)
        if shared.VERBOSE >= 2:
            self.show_history()

        return True
