#!/usr/bin/python3

import time
import datetime
import calendar
from datetime import datetime as dada

def int_time():
    return int(time.time())


def strptime(text, fmt):
    '''Alias for strptime'''
    return datetime.datetime.strptime(text, fmt).timestamp()



def midnight(now=None):
    "Return next midnight, optionally supply a datetime object to get a different day's midnight"
    if not now:
        now = dada.today()
    return dada(now.year, now.month, now.day).timestamp() + 86400


def seconds_since_midnight(now=None):
    '''
    if seconds:
        tim = time.localtime(seconds)
    else:
        tim = time.localtime()
    return tim.tm_hour * 3600 + tim.tm_min * 60 + tim.tm_sec + time.time() % 1
    '''
    if not now:
        now = time.time()
    return now + 86400 - midnight()


def diff_days(*args):
    '''Return days between two timestamps
    or between now and timestamp
    Ex: diff_days(time.time(), time.time()+86400)
    Ex: diff_days(timestamp)'''
    if len(args) == 2:
        start = args[0]
        end = args[1]
    else:
        end = args[0]
        start = time.time()
    diff = (dada.fromtimestamp(end) - dada.fromtimestamp(start))
    return diff.days + diff.seconds / 86400  # + diff.microseconds/86400e6


def add_date(src, years=0, months=0, days=0):
    "Add a number of years, months, days to date object"

    # Calculate new years and month
    new_y, new_m = src.year, src.month
    new_y += (new_m + months - 1) // 12 + years
    new_m = (new_m + months - 1) % 12 + 1

    # Replace years and month in date and limit days if month comes up short (like February has 28 days)
    new_d = min(calendar.monthrange(new_y, new_m)[-1], src.day)
    date = src.replace(year=new_y, month=new_m, day=new_d)

    # Add and days in
    if days:
        date += datetime.timedelta(days=days)
    return date


def local_time(timestamp=None, user_format=None, lstrip=True):
    '''Given a unix timestamp, show the local time in a nice format:
    By default will not show date, unless more than a day into future.Format info here:
    https://docs.python.org/3.5/library/time.html#time.strftime '''
    if not timestamp:
        timestamp = time.time()

    if user_format:
        fmt = user_format
    else:
        fmt = '%I:%M %p'
        if timestamp and time.localtime()[:3] != time.localtime(timestamp)[:3]:
            if time.localtime()[:2] != time.localtime(timestamp)[:2]:
                # New month
                fmt = '%Y-%m-%d'
            else:
                if diff_days(timestamp) < 7:
                    # New day of week
                    fmt = '%a %I:%M %p'
                else:
                    # New day in same month
                    fmt = '%m-%d %I:%M %p'

    if lstrip:
        return time.strftime(fmt, time.localtime(timestamp)).lstrip('0')
    else:
        return time.strftime(fmt, time.localtime(timestamp))



def _test():
    today = datetime.datetime(*datetime.datetime.now().timetuple()[:3])

    print('\nadd_date')
    for months in range(22):
        print(months, add_date(today, months=months))

    print('\nlocal_time')
    for extra in (0, 3600, 86400):
        print(extra, local_time(time.time() + extra))

    print('\nmidnight')
    print(midnight())

    print('\nseconds_since_midnight')
    print(seconds_since_midnight())


if __name__ == "__main__":
    _test()
