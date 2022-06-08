import sd.chronology as chronos

VERBOSE = 1

def aprint(*args, v=1, header='\n', **kargs):
    if VERBOSE >= v:
        print(header + chronos.local_time(), *map(str, args), **kargs)
