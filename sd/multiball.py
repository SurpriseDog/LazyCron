#!/usr/bin/python3
# MultiBall! https://www.youtube.com/watch?v=GpTPm1R4_AM
# Functions for interacting with multiple threads

# Check out dotter to watch spawned threads.

import time
import queue
import threading

# todo: look at hash_mouse for sharing data between multiprocessing threads

def spawn(func, *args, daemon=True, delay=0, **kargs):
    '''Spawn a function to run seperately and return the que
    waits for delay seconds before running
    Get the results with que.get()
    daemon = running in background, will shutdown automatically when main thread exits
    Check if the thread is still running with thread.is_alive()
    print('func=', func, id(func))'''
    # replaces fork_cmd, mcall

    def worker():
        if delay:
            time.sleep(delay)
        ret = func(*args, **kargs)
        que.put(ret)

    que = queue.Queue()
    # print('args=', args)
    thread = threading.Thread(target=worker)
    thread.daemon = daemon
    thread.start()
    return que, thread


class _TmanObj():
    "Used for ThreadManager"

    def __init__(self, func, *args, delay=0, **kargs):
        self.start = time.time()
        self.que, self.thread = spawn(func, *args, delay=delay, **kargs)

    def age(self):
        return time.time() - self.start

    def is_alive(self):
        return self.thread.is_alive()


class ThreadManager():
    "Maintain a list of threads and when they were started, query() to see if done."

    def __init__(self):
        self.threads = dict()

    def query(self, func, *args, delay=0, max_age=0, **kargs):
        "Start thread if new, return status, que.get()"
        serial = id(func)

        obj = self.threads.get(serial, None)
        if max_age and obj and obj.age() > max_age:
            print("Thread aged out")
            del obj
            obj = None
        if obj and obj.is_alive():
            print("Can't get results now, we got quilting to do!")
            return False, None
        if obj:
            del self.threads[serial]
            return True, obj.que.get()

        # print("Starting thread!")
        obj = _TmanObj(func, *args, delay=delay, **kargs)
        self.threads[serial] = obj
        return False, None

    def remove(self, func):
        "Remove thread if in dict"
        serial = id(func)
        if serial in self.threads:
            del self.threads[serial]


tman = ThreadManager()  # pylint: disable=C0103

'''Example:
while True:
    print('\n\nquery')
    ready, results = tman.query(is_busy)
    print('results =', results)
    if ready and results == True:
        print("todo going to sleep")
    time.sleep(4)
'''
