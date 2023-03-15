#!/usr/bin/python3

import time

class ReadState:
    "Maintains open file handles to read the state of a file without wasting resources"

    def __init__(self, verbose=False, limit=64, cleanup_age=86400):
        # Minimum age to keep an old unaccessed file around before cleaning it up
        # 0 = Don't cleanup
        self.cleanup_age = cleanup_age

        # There is a limit to the number of open file handles.
        # int(resource.getrlimit(resource.RLIMIT_NOFILE)[0] / 4)
        self.limit = limit


        # verbose =       1   Print a notification each time a new file opened
        # verbose =       2   Print a notification each time a file is accesssed
        self.verbose = verbose

        # Internals
        self._filenames = dict()         # dictionary of filenames to file handles
        self._history = dict()           # When was the last time file was opened?
        self._last_cleanup = time.time() # Cleanup old files, occassionally


    def read(self, filename, multiline=False, forget=False,):
        '''
        Read file data from a file, creating a new file handle if needed.

        forget =        open a file without maintaing open file handle
        multiline =     Return every stdout line instead of just the first.
        '''

        if self.verbose >= 2:
            print("Reading:", filename)

        # Open a file and don't add it to the log
        if forget:
            with open(filename, 'r') as f:
                if multiline:
                    return list(map(str.strip, f.readlines()))
                else:
                    return f.readline().strip()


        # Cleanup old unused file handles
        now = time.time()
        if self.cleanup_age and now - self._last_cleanup > self.cleanup_age / 2:
            self._last_cleanup = now
            for otime, name in self._history.items():
                if name == filename:
                    continue
                if now - otime > self.cleanup_age:
                    print("Removing old file handle:", name)
                    f = self._filenames[name]
                    del self._filenames[name]
                    del self._history[otime]
                    f.close()

        # Remove files if past the limit of file handles
        if len(self._filenames) >= self.limit:
            earliest = sorted(list(self._history.keys()))[0]
            name = self._history[earliest]
            print("\nToo many open handles for read_state!")
            print("Removing:", name)
            f = self._filenames[name]
            f.close()
            del self._filenames[name]
            del self._history[earliest]

        # Open the file
        if filename not in self._filenames:
            if self.verbose:
                print("Opening", '#' + str(len(self._filenames) + 1) + ':', filename)
            try:
                f = open(filename, 'r')
            except BaseException:
                raise ValueError("Could not open: " + filename)
            self._filenames[filename] = f
        else:
            f = self._filenames[filename]
            f.seek(0)
        self._history[now] = filename

        # Return data
        if multiline:
            return list(map(str.strip, f.readlines()))
        else:
            return f.readline().strip()


_READ_STATE_DEFAULT = ReadState()
def read_state(filename, **kargs):
    return _READ_STATE_DEFAULT.read(filename, **kargs)


def _tester():
    rs = ReadState(limit=1, verbose=True)
    print(rs.read('/proc/uptime'))
    print(rs.read('/proc/meminfo'))


if __name__ == "__main__":
    _tester()
