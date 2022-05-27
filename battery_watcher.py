#!/usr/bin/python3
# Popup a warning box when you battery is getting low and puts the computer to sleep
# Usage: ./battery_watcher.py <target power level>
# For testing mode run with:  ./battery_watcher.py test

# Requires tkinter for the standalone script: sudo apt install python3-tk

import os
import sys
import time

from sd.bash import quickrun
from sd.common import chunker, trailing_avg, read_val, read_file, list_get, Eprinter, sig
from sd.chronology import local_time, fmt_time, fmt_clock, msleep

eprint = Eprinter(verbose=1).eprint     # pylint: disable=C0103

def get_filename(expr, path='/sys/class/power_supply/'):
    "Custom filename finder for BatteryWatcher"
    for sub in os.listdir(path):
        for _paths, _dirs, names in os.walk(os.path.join(path, sub)):
            for name in names:
                if expr == name:
                    name = os.path.join(path, sub, name)
                    eprint("Using filename:", name)
                    return name
    else:
        # print("Could not find file:", expr, 'in', path)
        return None


class BatteryWatcher:
    "Keep track of the battery levels over time to predict when it will run out"

    def __init__(self):

        # Get battery filenames
        for cname, mname in [['charge_now', 'charge_full'], ['energy_now', 'energy_full']]:
            self.capacity = get_filename(cname)
            if self.capacity:
                self.max_power = int(read_file(get_filename(mname)))
                break
        else:
            self.capacity = get_filename('capacity')
            self.max_power = 100

        if not self.capacity:
            raise ValueError("Cannot find battery access file")
        else:
            print("Using file:", self.capacity)
            self.capacity = open(self.capacity)


        self.plug = open(get_filename('online'))
        self.levels = dict()                 # Dict of power level percents to timestamps
        self._charge = self.check_batt()     # Updated only with call to check_batt
        self.reset()

    def is_plugged(self):
        return bool(read_val(self.plug))

    def reset(self):
        "Reset the dictionary of levels if there's not a continuous time history of batt discharge"
        self.levels.clear()
        self.start = time.time()

    def check_batt(self):
        "Check update self.levels and returns battery level. 100 = Plugged in"
        if read_val(self.plug):
            self.reset()
            return 100
        else:
            charge = round(read_val(self.capacity) / self.max_power * 100, 1)
            if charge not in self.levels:
                self.get_rate()
            self.levels[charge] = int(time.time())
            self._charge = charge
            return charge

    def get_rate(self, printme=False):
        '''Get discharge time per power percent.
        Skips last level because it hasn't been exhausted yet.'''
        if len(self.levels) >= 3:
            rates = []
            for t1, t2 in chunker(sorted(self.levels.keys(), reverse=True)[:-1], overlap=True):
                power_delta = t1 - t2
                time_delta = self.levels[t2] - self.levels[t1]
                rates.append(time_delta / power_delta)
            ans = trailing_avg(rates[-10:])
            if printme and len(rates) >= 1:
                out = [sig(num/60, 1) for num in rates]
                print("Minutes between each percent level and trailing average:",
                      ', '.join(out), '=', sig(ans/60, 2))
            return ans
        return None

    def time_left(self, target, update=True):
        "Estimate seconds until power level will reach target"
        if update:
            charge = self.check_batt()
        else:
            charge = self._charge
        if charge <= target:
            return 0
        rate = self.get_rate()
        if rate:
            seconds = (charge - target) * rate
            return seconds
        return float('inf')

    def wait_until(self, target):
        "Wait until target is reached, then return"
        charge = 100
        while True:
            charge = self.check_batt()
            if charge <= target:
                return True
            if charge == 100 or charge - target > 20:
                missing = msleep(600)
            elif len(self.levels) < 3:
                # Can't make estimation with no data
                missing = msleep(60)
            else:
                seconds = self.time_left(target, update=False)
                missing = msleep(seconds / 5 if seconds > 100 else 20)
            if missing:
                print("Unaccounted for time during sleep:", fmt_time(missing), "Resetting measurements.")
                self.reset()


################################################################################

def angles(ang1, ang2):
    "Angles between two degrees (not radians)"
    res = abs(ang2 % 360 - ang1 % 360)
    if res > 180:
        return 360 - res
    else:
        return res

def rainbow(num):
    "Turn an integer into colors"
    deg = num % 360
    r = max(int((1 - angles(deg, 0) / 120) * 255), 0)
    g = max(int((1 - angles(deg, 120) / 120) * 255), 0)
    b = max(int((1 - angles(deg, 240) / 120) * 255), 0)
    # print(num, r, g, b)
    return '#%02x%02x%02x' % (r, g, b)
'''
for num in range(0, 360, 10):
    rainbow(num)
'''

class ShowCountdown:
    "Display a GUI countdown timer to end_time"

    def __init__(self, batt, target, testing_mode=False):
        self.batt = batt
        self.loop_id = 0
        self.testing_mode = testing_mode    # Don't actually put computer to sleep
        self.target = target        # Target battery percentage
        self.end_time = None        # Calculated time when target % reached
        self.grace_time = 2         # Time after end_time before it actually goes to sleep
        self.warn_time = 120        # Time remaining before popup window
        self.wait4popup()


    def wait4popup(self):
        "Wait until time is less than warning time, then popup window"
        self.batt.wait_until(self.target+10)
        levels = 0
        inf = float('inf')
        while True:
            time_left = self.batt.time_left(self.target)
            if time_left <= self.warn_time:
                break
            if levels != len(self.batt.levels):
                levels = len(self.batt.levels)
                if time_left < inf and levels >= 1:
                    print('\nETA:', local_time(time.time() + time_left).lstrip('0'),
                          'in', fmt_time(time_left, fields=1))
                    self.batt.get_rate(printme=True)
            if time_left == inf:
                missing = msleep(200)
            elif time_left < 200:
                missing = msleep(20)
            else:
                missing = msleep(time_left / 10)
            if missing:
                print("\nUnaccounted for time during sleep:", fmt_time(missing), "Resetting measurements.")
                self.batt.reset()

        if time_left < self.warn_time:
            time_left = self.warn_time
        self.end_time = time_left + time.time()
        self.popup()


    def popup(self):
        "Actual popup window"

        def delay():
            explanation.config(fg='black')
            self.end_time += self.warn_time

        def loop():
            now = time.time()
            time_left = self.end_time - now
            self.loop_id += 1

            if time_left < -self.grace_time:
                # Sleepy Time
                root.update()
                print("Putting computer to sleep...")

                if not self.testing_mode:
                    quickrun('systemctl', 'suspend')
                root.destroy()
                return

            # With less than 60 seconds left, show time rainbowing
            if time_left < 60:
                if time_left <= 0:
                    explanation.config(text="Going to sleep...", fg='black')
                    text = '0.00'
                else:
                    text = str(int(time_left)) + (':%.2f' % (time_left % 1))[2:]
                countdown.config(fg="red")
                explanation.config(fg=rainbow(time_left*180))
                interval = 20
            else:
                if self.loop_id % 600 == 0:
                    # Reestimate every minute
                    time_left = self.batt.time_left(self.target)
                    if time_left < 60:
                        time_left = 60
                    self.end_time = time_left + now
                text = fmt_clock(time_left).lstrip('0')
                interval = 100

            # Every 1 second check to see if battery plugged in
            if self.loop_id % (1000 // interval) == 0:
                charge = self.batt.check_batt()
                if charge >= 100:
                    root.destroy()
                    return


            countdown.config(text=text)
            root.update()
            root.after(interval, loop)

        # Popup the warning box
        root = tk.Tk()
        root.title("Battery Watcher")

        explanation = tk.Label(root, font=("Arial", 12))
        explanation.config(text="Battery Low! Your computer will enter sleep mode in:", font='Helvetica 16 bold')
        explanation.pack(pady=10)

        countdown = tk.Label(root, text="", font=("Helvetica", 40), justify='center')
        countdown.pack()

        delay_b = tk.Button(root, text="Delay "+fmt_time(self.warn_time),
                            command=delay, width=20, font=("Arial", 12))
        delay_b.pack()

        root.update()
        x = explanation.winfo_width() + 20
        y = delay_b.winfo_height() + delay_b.winfo_y() + 20
        root.geometry(str(x) + 'x' + str(y))

        root.lift()
        root.after(10, loop)
        root.mainloop()



def _main():
    "Wait until the battery gets to target level and then popup a warning"
    batt = BatteryWatcher()
    testing_mode = bool(list_get(sys.argv, 1).lower().startswith('test'))

    while True:
        if testing_mode:
            target = batt.check_batt() - 8
            print("Using target of:", int(target), 'percent')
        else:
            target = int(list_get(sys.argv, 1, 5))
        ShowCountdown(batt, target, testing_mode=testing_mode)
        while not batt.is_plugged():
            time.sleep(600)
        batt.reset()


if __name__ == "__main__":
    import tkinter as tk
    _main()
