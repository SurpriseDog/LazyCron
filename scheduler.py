#!/usr/bin/python3

import os
import re
import csv
import time
import gzip
import shutil
import bisect
import shlex
import random
import tarfile
import datetime
import subprocess
from datetime import datetime as dada

import shared
import sd.chronology as chronos

from shared import aprint
from timewatch import get_idle

from sd.msgbox import msgbox
from sd.columns import indenter
from sd.common import safe_filename, error, check_internet, spawn, quickrun
from sd.common import search_list, DotDict, warn, unique_filename, ConvertDataSize, rfs


class Reqs:
    "User requirements field"

    def __init__(self,):
        # Requirements measured in units of time
        self.time_reqs = ('idle', 'busy', 'elapsed', 'today', 'random', 'timeout', 'delay', 'loopdelay')

        # Requirements measured in KB, MB...
        self.data_reqs = ('disk', 'network')

        # String only
        self.string_reqs = ('ssid', 'environs')

        # Requirements to run processes, These are default values if no argument given by user
        self.reqs = DotDict(plugged=True,
                            unplugged=True,
                            idle=10 * 60,
                            busy=10 * 60,
                            elapsed=10 * 60,
                            closed=True,
                            open=True,
                            random=86400,
                            start=1,
                            retry=3,
                            loop=0,
                            shell=True,
                            environs='',
                            loopdelay=1,
                            delay=60,
                            delaymult=2,
                            timeout=3600,
                            nologs=True,
                            localdir=True,
                            online=True,
                            today=10 * 60,
                            skip=1,
                            ssid="",
                            max=0,
                            reps=1,
                            nice=5,
                            disk=shared.LOW_DISK,
                            network=shared.LOW_NET,
                            cpu=shared.LOW_CPU,
                            )

        # Aliases to self.reqs
        self.aliases = dict(plug='plugged',
                            unplug='unplugged',
                            lazy='idle',
                            rand='random',
                            startup='start',
                            no_logs='nologs',
                            local_dir='localdir',
                            shut='closed',
                            wait='delay',
                            wifi='ssid',
                            environmentals='environs',
                            doubler='delaymult',
                            retrydelay='loopdelay',
                            retry_delay='loopdelay',
                            loop_delay='loopdelay',
                            doubledelay='delaymult',
                            multdelay='delaymult',
                            lan='ssid',
                            kill='timeout',
                            skipped='skip',
                            internet='online',
                            used='busy',
                            usage='busy',
                            maximum='max',
                            disc='disk',
                            repititions='reps',
                            repetitions='reps',
                            )


        # Swap plugged with unplugged and so on...
        self.inversions = dict(unplugged='plugged', open='closed')

        # Needed programs to use named reqs
        self.needed = dict(cpu='mpstat', network='sar', disk='iostat')
        assert all([key in self.reqs for key in self.needed])

        #
        assert all([key in self.reqs for key in self.time_reqs + self.data_reqs + self.string_reqs])

        # Check for errors in reqs:
        # No repeats between aliases and real reqs
        assert not set(self.aliases.keys()) & set(self.reqs.keys())
        # All values in aliases are legit reqs
        assert all([val in self.reqs.keys() for val in self.aliases.values()])

    def __call__(self, value):
        if value in self.reqs:
            return self.reqs[value]
        else:
            return None

    def reset(self,):
        self.reqs = DotDict()

    def print(self,):
        # Print reqs
        out = {}
        for key, val in sorted(self.reqs.items()):
            if key in self.data_reqs:
                val = rfs(val) + '/s'
            if key in self.time_reqs and val >= 300:
                val = chronos.fmt_time(val)
            out[key] = val
        print('Reqs: ', out)

    def req_okay(self, req):
        "Check that the req is okay to use"
        def check(program):
            if not shutil.which(program):
                warn("Install", program, "to use the", req, "req")
                return False
            return True

        if req in self.needed:
            return check(self.needed[req])
        return True

    def get_environs(self):
        "Special handling for environs"
        if 'environs' in self.reqs:
            out = dict()
            for arg in self.reqs.environs.split('$'):
                vals = list(csv.reader([arg.strip()], delimiter='='))[0]
                vals = list(map(str.strip, vals))
                if len(vals) != 2:
                    warn("Corrupted environ string. Expected format: environs VAL1=TEXT $ VAL2=TEXT")
                else:
                    out[vals[0]] = vals[1]
            # print('Loaded environ:', out)
            self.reqs.environs = out


    def process_reqs(self, args):
        "Process requirements field"
        found = []

        for arg in args:
            if not arg.strip():
                continue
            split = arg.lower().strip().split()
            arg = split[0].rstrip(':')
            val = (' '.join(split[1:])).strip()
            match = search_list(arg, self.reqs.keys(), get='first')
            if not match:
                match = search_list(arg, self.aliases.keys(), get='first')
                if match:
                    match = self.aliases[match]
            if not match:
                error("Can't find requirement:", arg)
            if not self.req_okay(match):
                continue

            # Get default value if not supplied
            if not val:
                val = self.reqs[match]

            # deal with plugged/unplugged closed/open...
            if match in self.inversions:
                match = self.inversions[match]
                inverted = True
            else:
                inverted = False

            # Non numeric conversions
            if match in self.time_reqs:
                val = chronos.convert_user_time(val, default='minutes')
            elif match in ('plugged', 'closed', 'online'):
                val = bool(val)
            elif match in self.data_reqs:
                val = re.sub('second[s]*', 's', val)
                val = re.sub('[/\\\\]*[s]$', '', val)
                val = ConvertDataSize()(val)
            elif match in self.string_reqs:
                val = val.strip("'").strip('"').strip()
            else:
                try:
                    val = int(val)
                except ValueError:
                    val = float(val)

            if inverted:
                val = not val


            found.append(match)
            self.reqs[match] = val

        # Delete reqs that were not specified by user
        for key in list(self.reqs.keys()):
            if key not in found:
                del self.reqs[key]

        self.get_environs()


def process_date(src):
    '''Process a date range into special format:
    Examples:
    (start, end, 'week') - ex: (1, 3, 'week')
    (start, end, 'month')
    (1, 3, 'week') = 'tuesday to thursday'          (range of days every week)
    (3, 7, 'month') = '3rd to 7th'                  (range of days every month)
    ((10, 7), (3, 3) = 'October 7th to March 3rd'   (range of dates every year)

    '''

    section = re.split('-| to ', src)
    try:
        days, cycle = list(zip(*map(chronos.udate, section)))
    except ValueError:
        error("Cannot understand text:", src)

    if len(set(cycle)) != 1:
        error("Cycle length in", src, "must be the same")
    cycle = cycle[0]
    start = days[0]
    if len(days) == 1:
        end = start
    else:
        end = days[1]

    return start, end, cycle


def next_day(day, cycle, today=None):
    "Given a process_date formatted data, return the next occurence"
    if not today:
        today = dada(*dada.now().timetuple()[:3])

    if cycle == 'week':
        delta = datetime.timedelta((day - today.weekday()))
    elif cycle == 'month':
        delta = datetime.timedelta((day - today.day))
    elif cycle == 'year':
        month, day = day
        date = today.replace(month=month, day=day)
        if date < today:
            date = add_cycle(date, cycle)
        return date
    else:
        error('cycle', cycle, "unsupported")

    date = today + delta
    if date < today:
        date = add_cycle(date, cycle)
    return date


def add_cycle(date, cycle, count=1):
    "Add a cycle to a date"
    if cycle == 'week':
        return chronos.add_date(date, days=7*count)
    elif cycle == 'month':
        return chronos.add_date(date, months=1*count)
    elif cycle == 'year':
        return chronos.add_date(date, years=1*count)
    else:
        raise ValueError("Unkown cycle length:", cycle)
    return date



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
        self.next_run = 0           # Next time the script can run

        self.elapsed_freq = 0       # Run every elapsed time
        self.elapsed_next = 0       # Next time allowed to run by elapsed_freq

        self.args = args            # Preserve initial setup args
        self.thread = None          # Thread starting running process
        self.verbose = shared.VERBOSE

        self.reqs = Reqs()
        self.process_args()                         # Process data lines
        self.cmd = self.process_path(args['path'])
        self.calc_window()


    def process_path(self, path):
        "Process the command line path from args"

        def alert(*args):
            warn(*args)
            msgbox(*args)

        path = path.strip()
        if not path:
            return alert("No path specified")

        testing = False
        if path.startswith('#'):
            testing = True
            path = path.lstrip('#')


        if not self.reqs('shell'):
            cmd = shlex.split(path)
            if cmd[0].lower().startswith('msgbox'):
                cmd[0] = os.path.abspath('sd/msgbox.py')
            program = cmd[0]
        else:
            cmd = [path]
            program = shlex.split(path)[0]

        # Get self.name
        name = os.path.basename(program) + ' ' + ' '.join(cmd[1:])
        name = list(indenter(name.strip(), wrap=64))
        if len(name) > 1:
            self.name = name[0].rstrip(',') + '...'
        else:
            self.name = name[0].rstrip(',')

        # Verify it can be run:
        if not testing and not shutil.which(program):
            return alert("Could not find program:", program)

        if self.reqs('localdir') and os.path.exists(path) and not os.path.isabs(path):
            return alert("Can't mix relative paths when localdir is turned on:", path)


        # add the # back in
        if testing:
            cmd[0] = '#' + cmd[0]
        return cmd




    def process_time(self, section):
        vals = chronos.convert_ut_range(section, default='hours')
        if len(vals) == 2:
            self.window.append([vals[0], vals[1]])
        else:
            error("Can't read time:", section)


    def process_freq(self, args):
        "Process frequency and elapsed frequency field"
        freq_trigger = False
        for arg in args:
            for term in ['elapsed', 'used', 'usage', 'in use', 'busy', 'inuse', 'not idle', 'every']:
                if term in arg:
                    arg = arg.replace(term, '').strip()
                    self.elapsed_freq = chronos.convert_user_time(arg, default='minutes')
                    self.elapsed_next = self.elapsed_freq
                    break
            else:
                freq_trigger = True
                self.freq = chronos.convert_user_time(arg, default='minutes')

        if self.elapsed_freq and not freq_trigger:
            self.freq = 0


    def process_args(self):
        args = self.args
        for key, values in args.items():
            key = key.lower()
            values = str(values).lower()

            # Handle star values
            if values == '*':
                if key == 'reqs':
                    self.reqs.reset()
                elif key == 'time':
                    self.window = [[0, 86400]]
                continue

            else:
                # values = values.split(',')
                values = list(csv.reader([values]))[0]

                if key == 'reqs':
                    self.reqs.process_reqs(values)
                elif key == 'frequency':
                    self.process_freq(values)
                else:
                    for val in values:
                        if key == 'time':
                            self.process_time(val)
                        if key == 'date':
                            self.date_window.append(process_date(val))



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
        print('cmd: ', self.cmd)

        self.reqs.print()

        print('In Window:', self.in_window())
        if self.next_run:
            print('Next_run:', chronos.local_time(self.next_run))
        if self.elapsed_freq:
            print('Elapsed freq:', chronos.fmt_time(self.elapsed_freq))
            print('Next Elapsed:', chronos.fmt_time(self.elapsed_next))


    def running(self):
        "Check if process is already running."
        if self.thread and self.thread.is_alive():
            return True
        return False
        # Search system wide
        # return ps_running(self.cmd)


    def calc_date(self, extra=0):
        "Get next date range when allowed to run"
        if not self.date_window:
            return None     # Shouldn't be run
        today = dada(*dada.now().timetuple()[:3]) + datetime.timedelta(days=extra)
        new_start = dada(today.year + 1000, 1, 1)           # farthest future
        new_stop = dada(11, 11, 11)

        # For start date, end date, cycle type in date window
        for sd, ed, cycle in self.date_window:
            start = next_day(sd, cycle, today)
            stop = next_day(ed, cycle, today)

            # If start is after stop, then we may be in the date window
            if today <= stop <= start:
                start = add_cycle(start, cycle, -1)

            if start < new_start:
                new_start = start
                new_stop = stop

        # testing: reload(scheduler); a = scheduler.App({'time': '11pm-2am', 'frequency': '*', 'reqs': '*', 'path': '#test', 'date' : 'sat-mon'}); a.calc_date()    # pylint: disable=line-too-long
        return new_start, new_stop


    def calc_window(self):
        "Calculate the next start and stop window for the proc in unix time"
        inf = float("inf")
        now = time.time()
        midnight = round(now - chronos.seconds_since_midnight())
        if self.date_window:
            self.start, self.stop = map(dada.timestamp, self.calc_date(extra=1))

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
                    self.start, self.stop = map(dada.timestamp, self.calc_date(extra=1))
                get_first()
        else:
            self.stop += 86400

        if self.history and (self.window or self.date_window):
            if self.verbose >= 3:
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


    def ready(self, twatch, polling_rate, busy):
        "Is the process ready to be run?"
        now = time.time()

        # Check if process is already running.
        if self.thread and self.thread.is_alive():
            self.alert("Still running!")
            return False

        if self.window or self.date_window:
            if not self.in_window():
                self.alert("Outside of time window")
                return False

        if self.next_run and now < self.next_run:
            self.alert("Next run at", chronos.local_time(self.next_run))
            return False

        if self.elapsed_freq:
            if twatch.elapsed < self.elapsed_next:
                self.alert("Elapsed freq not reached")
                return False


        # Check App requirements.
        # Not a match statement. No increase in speed and breaks compatability with python versions < 3.10
        # Future maybe put if verbose > ? before each alert statement for optimization, but probably not needed
        reqs = self.reqs.reqs
        if reqs:

            # Usage requirements:
            if 'idle' in reqs:
                if twatch.idle < reqs.idle or get_idle() < reqs.idle:
                    self.alert("Idle time not reached")
                    return False
            if 'busy' in reqs and twatch.usage() < reqs.busy:
                self.alert("Not in use long enough", twatch.usage(), '<', reqs.busy)
                return False
            if 'elapsed' in reqs and twatch.elapsed < reqs.elapsed:
                self.alert("Elapsed not reached", twatch.elapsed, '<', reqs.elapsed)
                return False
            if 'today' in reqs and twatch.today_elapsed < reqs.today:
                self.alert("Today elapsed not reached", twatch.today_elapsed, '<', reqs.today)
                return False
            if 'random' in reqs and random.random() > polling_rate / reqs.random:
                # Random value not reached
                self.alert("Random value not reached: 1 in", int(1 / (polling_rate / reqs.random)))
                return False

            # History requirements:
            if 'start' in reqs and len(self.history) >= reqs.start:
                return False
            if 'max' in reqs and len(self.history) >= reqs.max:
                self.alert("Max number of times reached")
                return False
            if 'reps' in reqs:

                # Start time if in window, otherwise midnight:
                start = self.start if self.start else now - chronos.seconds_since_midnight()
                count = len(self.history) - bisect.bisect_left(self.history, start)

                # Fixed bug where skipped runs counted towards reps
                if 'skip' in reqs:
                    count -= reqs.skip

                if count >= reqs.reps:
                    self.alert("Max number of reps reached:", count, 'since', chronos.local_time(start))
                    return False

            # Machine requirements:
            for name, func in [('cpu', busy.get_cpu), ('disk', busy.get_disk), ('network', busy.get_net)]:
                if name in reqs:
                    val = func()
                    if val is None:
                        # None value = thread not ready yet
                        return False
                    if val >= reqs[name]:
                        self.alert(name, "usage too high to continue")
                        return False

            # State requirements:
            # Keep last to avoid unnecessary checks
            if 'closed' in reqs and reqs.closed == shared.COMP.lid_open():
                self.alert("Wrong lid state")
                return False
            if 'plugged' in reqs and reqs.plugged != shared.COMP.plugged_in():
                self.alert("Wrong plug state")
                return False
            if 'ssid' in reqs and reqs.ssid.lower() != shared.COMP.get_ssid().lower():
                self.alert("Wrong network id")
                return False
            if 'online' in reqs and not check_internet():
                self.alert("Not Online")
                return False

        return True


    def run(self, twatch, testing_mode, skip_mode=False):
        "Run the process in seperate thread while writing output to log."
        now = time.time()

        if not (skip_mode and self.start):
            # Fixes minor buy where skip mode ensures that a process would NEVER start
            self.history.append(now)

        if skip_mode:
            testing_mode = True

        # If no frequency was specifed, then it will run every day. Note! 0 != None
        if self.freq is None:
            # Set to midnight
            self.next_run = now + 86400 - chronos.seconds_since_midnight()
        elif self.freq:
            # Otherwise add freq
            self.next_run = now + self.freq
        if self.elapsed_freq:
            self.elapsed_next = twatch.elapsed + self.elapsed_freq


        # Must be in run to trigger self.next_run
        reqs = self.reqs.reqs
        if 'skip' in reqs and len(self.history) <= reqs.skip:
            self.alert("Skip", len(self.history), 'of', reqs.skip, v=2)
            return

        if self.cmd[0].lstrip().startswith('#'):
            testing_mode = True
        if testing_mode:
            text = "Did not start process"
        else:
            text = "Started process"
            filename = safe_filename(self.name + '.' + str(int(now)))
            _, self.thread = spawn(run_thread,
                                   self.cmd,
                                   log=os.path.abspath(os.path.join(shared.LOG_DIR, filename)),
                                   reqs=self.reqs,
                                   name=self.name,
                                   )

        self.alert(text, v=1)
        if self.verbose >= 2:
            self.show_history()


def run_thread(cmd, log, reqs, name):
    "Run a command in it's own thread, and save stdout and stderr"

    time.sleep(reqs('delay') or 0)
    if reqs('nice'):
        os.nice(reqs('nice') - shared.NICE)

    retry = reqs('retry')

    # Delay after each loop
    loopdelay = reqs('loopdelay') if reqs('loopdelay') is not None else 60

    # Default to doubling delay each time if running in retry mode
    delaymult = reqs('delaymult')               # Multiply delay by this amount each time
    if delaymult is None:
        if retry:
            delaymult = 2
        else:
            delaymult = 1

    # Loop in retry and loop modes
    counter = 0
    loops = reqs('loop')

    messages_sent = 0
    def send_msg():
        "Send message on error (only once)"
        nonlocal messages_sent
        if code and messages_sent < 1:
            print()
            warn(name, "\nReturned code", code)
            print("Errors in:", log)
            quickrun('sd/msgbox.py', name, "returned code", str(code))
            messages_sent += 1

    while True:
        counter += 1

        if counter >= 2:
            loopdelay *= delaymult

        code, elapsed = run_proc(cmd, log, reqs, attempt=counter)

        # Run this script again if requested (does not count toward reps)
        if retry:
            if code != 0 and (counter < retry or retry == 0):
                time.sleep(loopdelay)
                aprint("Retry", counter + 1, '::', name)
                continue
        if loops is not None:
            send_msg()
            if counter < loops or loops == 0:
                time.sleep(loopdelay)
                aprint("Loop", counter + 1, '::', name)
                continue
        break
    send_msg()

    if not code:
        msg = ' '.join((name, 'finished after', chronos.fmt_time(elapsed)))
        if counter > 1:
            msg += " on run number " + str(counter)
        aprint(msg)


def run_proc(cmd, log, reqs, attempt):
    "Actually run the process"

    # Set output and error files
    folder, file = os.path.split(log)
    log = os.path.join(folder, safe_filename(file))

    if attempt >= 2:
        log = log + '.' + str(attempt)

    ofilename = unique_filename(log + '.log')
    efilename = unique_filename(log + '.err')
    ofile = open(ofilename, mode='a')
    efile = open(efilename, mode='a')

    try:
        start = time.perf_counter()
        ret = subprocess.run(cmd, check=False, stdout=ofile, stderr=efile,
                             cwd=os.path.dirname(cmd[0]) if reqs('localdir') else None,
                             shell=reqs('shell') or False,
                             timeout=reqs('timeout'),
                             env=reqs('environs') or os.environ,
                             )
        elapsed = time.perf_counter() - start
        code = ret.returncode
    except subprocess.TimeoutExpired:
        print("Timeout reached for command:", cmd)
        code = 1

    # Close output files
    oflag = bool(ofile.tell())      # Does the file have data in it?
    eflag = bool(efile.tell())
    ofile.close()
    efile.close()


    # Remove logs if returned 0
    if not code and bool(reqs('nologs')):
        if oflag:
            os.remove(ofilename)
        if eflag:
            os.remove(efilename)
    else:
        # Remove file if nothing was written to them
        if not oflag:
            os.remove(ofilename)
        if not eflag:
            os.remove(efilename)

    return code, elapsed


def compress_logs(dirname, minimum=5, month=-1, overwrite=False, exts=('.log', '.err')):
    '''Add last months log files to tar.gz
    minimum = min number of files to compress (and delete)
    month = month to compress, 0 = current, -1 = last month and so on
    overwrite = overwrite existing .tar.gz
    exts = file extensions to add to tar, None = All files
    '''
    # Future: Gather up last years .tar.gz files and combine them?
    # https://stackoverflow.com/q/2018512/11343425

    cur = os.getcwd()
    os.chdir(dirname)       # Needed for relative paths

    def compress():
        "Worker function"

        today = dada(*dada.now().timetuple()[:3])
        start = chronos.add_date(today, months=month).replace(day=1)
        end = chronos.add_date(start, months=1)
        oname = start.strftime("%Y.%m.%B_logs.tar.gz")
        oname = os.path.join('Archived Logs', oname)

        if not overwrite and os.path.exists(oname):
            return False

        files = []
        for entry in os.scandir(dirname):
            name = entry.name
            if not entry.is_dir():
                if not exts or os.path.splitext(name)[-1] in exts:
                    stat = entry.stat(follow_symlinks=False)
                    if start.timestamp() <= stat.st_mtime <= end.timestamp():
                        files.append(name)

        if len(files) >= minimum:
            os.makedirs('Archived Logs', exist_ok=True)
            print("Compressing files from:", start.timetuple()[:3], "to", end.timetuple()[:3])
            with tarfile.open(oname, "w:gz") as tar:
                for name in files:
                    tar.add(name)

            # Verify gzip
            with gzip.open(oname, 'rb') as f:
                while f.read(1024*1024):
                    pass

            # Delete files once safely in archive
            for name in files:
                os.remove(name)
            print(len(files), "files have been compressed into", oname)
            return True
        return False

    status = compress()
    os.chdir(cur)
    return status
