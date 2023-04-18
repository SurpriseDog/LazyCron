#!/usr/bin/python3


import re
import csv
import shutil

import shared
import sd.chronology as chronos
from sd.common import DotDict, rfs, warn, search_list, error, ConvertDataSize


# Requirements to run processes, These are default values if no argument given by user
# Documentation for each one can be found in Readme.Md in the Requirements section
REQS = dict(
    plugged=True,
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
    lowbatt=10,
    showpid=True,
    minbatt=50,
    shell=True,
    wake=True,
    suspend=True,
    environs='',
    loopdelay=1,
    delay=60,
    delaymult=2,
    timeout=3600,
    nologs=True,
    noerrs=True,
    directory=None,
    localdir=True,          # Phased out. Now everything runs in localdir by default. Expect this line to be removed in future release.
    online=True,
    today=10 * 60,
    skip=1,
    ssid="",
    max=0,
    reps=1,
    nice=8,
    disk=shared.LOW_DISK,
    network=shared.LOW_NET,
    cpu=shared.LOW_CPU,
    )


# Aliases to Requirements
ALIASES = dict(
    plug='plugged',
    unplug='unplugged',
    lazy='idle',
    rand='random',
    startup='start',
    no_logs='nologs',
    local_dir='localdir',
    shut='closed',
    low_batt='lowbatt',
    cwd='directory',
    dir='directory',
    batt='lowbatt',
    battery='lowbatt',
    highbatt='minbatt',
    minbattery='minbatt',
    pid='showpid',
    wait='delay',
    wifi='ssid',
    noerrors='noerrs',
    no_errs='noerrs',
    no_errors='noerrs',
    sleep='suspend',
    slept='suspend',
    unsuspend='wake',
    woke='wake',
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


class Reqs:
    "User requirements field"

    def __init__(self,):
        # Requirements measured in units of time
        self.time_reqs = ('idle', 'busy', 'elapsed', 'today', 'random', 'timeout', 'delay', 'loopdelay')

        # Requirements measured in KB, MB...
        self.data_reqs = ('disk', 'network')

        # String only
        self.string_reqs = ('ssid', 'environs', 'directory')

        # Requirements to run processes, These are default values if no argument given by user
        self.reqs = DotDict(REQS)

        # Aliases to self.reqs
        self.aliases = ALIASES

        # Swap plugged with unplugged and so on...
        self.inversions = dict(unplugged='plugged', open='closed')

        # Needed programs to use named reqs
        self.needed = dict(network='sar', disk='iostat')
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
            self.reqs.environs = out


    def process_reqs(self, args):
        "Process requirements field"
        found = []

        for arg in args:
            if not arg.strip():
                continue
            split = arg.lower().strip().split()
            arg = split[0].rstrip(':')
            val = (' '.join(split[1:])).strip().rstrip('%')
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
                # Numeric conversions
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
