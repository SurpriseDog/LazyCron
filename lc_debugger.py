#!/usr/bin/python3

import shared
from sd.common import search_list

class Debugger:
    '''Hidden debug tool - Read user input and print status while running
    activate with --debug on command line
    type debug for list of commands

    '''

    def __init__(self, twatch, schedule_apps, user_args):
        self.twatch = twatch
        self.schedule_apps = schedule_apps
        self.uargs = user_args


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
            print(self.uargs)

        # Changing verbose requires special handling
        elif first == 'verbose':
            try:
                val = int(tail)
            except ValueError:
                return
            shared.VERBOSE = val
            for app in self.schedule_apps:
                app.verbose = val

        elif first == 'debug':
            print("Commands: time all vars reqs print run start args verbose")
            print("Or change user arguments by typing arg in this list")
            print(self.uargs)

        # Change other user arguments
        elif first in self.uargs:
            try:
                val = cmd.split()[1]
            except IndexError:
                return
            try:
                val = int(val)
            except ValueError:
                return
            self.uargs[first] = int(val)
            print(self.uargs)

        else:
            print("Unknown command:", cmd, 'type debug for list of commands.')
        print()
