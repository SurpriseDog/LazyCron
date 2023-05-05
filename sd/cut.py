#!/usr/bin/python3
# Convert user time text into date

import re
import time
from collections import Counter

from sd.common import warn
from sd.common import search_list

def _gen_conversions():
    "Generate user time conversions"
    day = 3600 * 24
    year = 365.2422 * day

    conversions = dict(
        seconds=1,
        minutes=60,
        hours=3600,
        days=day,
        weeks=7 * day,
        months=30.4167 * day,
        years=year,
        decades=10 * year,
        centuries=100 * year,
        century=100 * year,
        millenia=1000 * year,
        millenium=1000 * year,

        # Esoteric:
        fortnight=14 * day,
        quarter=30.4167 * day * 3,
        jubilees=50 * year,
        biennium=2 * year,
        gigasecond=1e9,
        aeons=1e9 * year, eons=1e9 * year,
        jiffy=1 / 60, jiffies=1 / 60,
        shakes=1e-8,
        svedbergs=1e-13,
        decasecond=10,
        hectosecond=100,

        # Nonstandard years
        tropicalyears=365.24219 * day,
        gregorianyears=year,
        siderealyears=365.242190 * day,

        # <1 second
        plancktimes=5.391e-44, plancks=5.391e-44,
        yoctoseconds=1e-24, ys=1e-24,
        zeptoseconds=1e-21, zs=1e-21,
        attoseconds=1e-18,
        femtoseconds=1e-15, fs=1e-15,
        picoseconds=1e-12, ps=1e-12,
        nanoseconds=1e-09, ns=1e-9,
        microseconds=1e-06, us=1e-6,
        milliseconds=1e-3, ms=1e-3)
    conversions['as'] = 1e-18
    return conversions

CONVERSIONS = _gen_conversions()


def match_conversion(text, conversions):
    "match text against a list of conversions"
    if text in conversions:
        return conversions[text]
    matches = search_list(text, conversions.keys())
    if len(matches) == 1:
        return conversions[matches[0]]
    elif len(matches) > 1:
        if len({conversions[m] for m in matches}) == 1:
            return conversions[matches[0]]
        else:
            warn("Multiple Matches found for:", text)
            for match in matches:
                print("\t", match.title())
            raise ValueError
    return None


def udate(text):
    '''
    Convert a user formatted date into a number of days and length of cycle
    S = Sunday, Sa = saturday
    3-7 = days of month, January 9, January 9th, Jan 2nd (throw away 2 digits after number)
    Per convention with datetime, weeks start on monday
    '''
    text = str(text).strip().lower()
    digits = sum([char.isdigit() for char in text])

    # Extract count (if available)
    # Example: Every 2nd Tuesday
    count = 1
    if digits < len(text):
        match = re.match('^[0-9][0-9]*', text)
        if match and len(match.group()) > 0:
            count = int(match.group())
            if len(text) <= 4:
                text = re.sub('^[0-9]*[^ ]{0,2}', '', text)
            if ' ' in text:
                text = re.sub('^[0-9]*[^ ]{0,2} ', '', text)


    # Count the remaining digits
    text = text.strip()
    digits = sum([char.isdigit() for char in text])
    # print('count', count, 'digits', digits, 'text', text)

    if not text:
        return count, 'month'

    # Match Tu T = Tuesday
    if digits == 0 and text:
        days = dict(
            m=0,
            monday=0,
            munday=0,
            t=1,
            tu=1,
            tuesday=1,
            tuseday=1,
            twosday=1,
            toosday=1,
            w=2,
            wednesday=2,
            wensday=2,
            r=3,
            h=3,
            th=3,
            thursday=3,
            thorsday=3,
            f=4,
            friday=4,
            fryday=4,
            s=5,
            saturday=5,
            u=6,
            sunday=6,
        )
        if len(text) >= 2:
            text = text.rstrip('s')
        new = match_conversion(text, days)
        if new is not None:
            return (count - 1) * 7 + new, 'week'

    # March 3
    if digits < len(text):
        day = 1
        month = time.strptime(text[:3], '%b').tm_mon
        text = re.sub('^[^0-9]*', '', text).strip()
        if text:
            day = int(re.sub('[^0-9]*', '', text))
        # today = dada(*dada.now().timetuple()[:3])
        return (month, day), 'year'


    # Just digits
    return int(text), 'month'


def convert_ut_range(unum, **kargs):
    "User time ranges like 3-5pm to machine readable"
    unum = unum.lower()
    if 'to' in unum:
        unum = unum.split('to')
    else:
        unum = unum.split('-')
    unum = list(map(str.strip, unum))

    count = Counter([item[-2:] for item in unum])
    pm = count['pm']
    am = count['am']
    if (pm or am) and not all([pm, am]):
        unit = 'pm' if pm else 'am'
        value = None        # Value of last time encountered
        for x, _ in enumerate(unum):
            if unum[x]:
                if unum[x].endswith(unit):
                    value = convert_user_time(unum[x].strip('pm').strip('am'))
                else:
                    if value is not None and convert_user_time(unum[x]) < value:
                        continue
                    unum[x] = unum[x] + unit
    return [convert_user_time(item, **kargs) for item in unum]

# Test: lmap(fmt_time, *convert_ut_range('3-5pm'))


def convert_user_time(unum, default='seconds'):
    '''Convert a user input time like 3.14 days to seconds
    Valid: 3h, 3 hours, 3 a.m., 3pm, 3:14 am, 3:14pm'''
    unum = str(unum).strip().lower()
    if ',' in unum:
        return sum(map(convert_user_time, unum.split(',')))
    if not unum:
        return 0

    # Primary units
    primary = "seconds minutes hours days months years".split()

    # 12 am/pm fix
    if re.match('12[^1234567890].*am', unum) or unum == '12am':
        unum = unum.replace('12', '0')
    if re.match('12[^1234567890].*pm', unum) or unum == '12pm':
        unum = unum.replace('12', '0')

    # Text processing:
    text = unum.lstrip('0123456789. \t:')
    num = unum.replace(text, '').strip()

    if ':' in num:
        # Convert a num like 3:14:60 into fractions of 60
        seconds = 0
        for x, t in enumerate(num.split(':')):
            seconds += float(t) / 60**x
        num = seconds

    num = float(num)
    if text:
        text = text.replace('.', '').strip().replace(' ', '')
        if text == 'am':
            return num * 3600
        elif text == 'pm':
            return num * 3600 + 12 * 3600
        else:
            # Match the text with the first unit found in units so that 3m matches minutes, not months
            unit = search_list(text, primary, get='first')
            if not unit:
                # Otherwise search for less commonly used units in entire list
                unit = match_conversion(text, CONVERSIONS)
            else:
                unit = CONVERSIONS[unit]
            return num * unit
    else:
        return num * CONVERSIONS[default]


def _tester():
    # Testing:

    dates = "3rd", 3, 'Friday', '3rd friday', '3 friday', 'march 3', 'march3rd'
    # '3 March', '3March'
    for text in dates:
        print(text)
        print(*udate(str(text)), '\n')


    while True:
        text = input('\n\nInput text to convert: ')
        try:
            print(udate(text))
        except Exception:       # pylint: disable=W0703
            print(traceback.format_exc())

if __name__ == "__main__":
    import traceback
    _tester()
