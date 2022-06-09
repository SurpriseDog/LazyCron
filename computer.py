#!/usr/bin/python3

import os
from sd.common import read_val, read_state, read_file, warn


def get_filename(expr, path='/sys/class/power_supply/', verbose=0):
    "Custom filename finder for Computer"
    for sub in os.listdir(path):
        for _paths, _dirs, names in os.walk(os.path.join(path, sub)):
            for name in names:
                if expr == name:
                    name = os.path.join(path, sub, name)
                    if verbose:
                        print("Using filename:", name)
                    return name
    else:
        # print("Could not find file:", expr, 'in', path)
        return None

class Computer:
    "Return state values of computer or defaults if unavailable"


    def __init__(self, verbose=0):

        # Plugged in
        plugged = get_filename('online')
        if plugged:
            if verbose:
                print("Using plugged in access file:", plugged)
            self._plugged = open(plugged)

        # Lid open
        self._lid = "/proc/acpi/button/lid/LID0/state"

        # Battery capacity
        for cname, mname in [['charge_now', 'charge_full'], ['energy_now', 'energy_full']]:
            self._capacity = get_filename(cname)
            if self._capacity:
                self.max_power = int(read_file(get_filename(mname)))
                break
        else:
            self._capacity = get_filename('capacity')
            self.max_power = 100
        if not self._capacity:
            warn("Cannot find battery access file")
        else:
            if verbose:
                print("Using battery capacity file:", self._capacity)
            self._capacity = open(self._capacity)

    def lid_open(self,):
        if self._lid:
            return read_state(self._lid).split()[1] == "open"
        else:
            # Fake answer if can't determine state
            return "open"

    def get_capacity(self,):
        if self._capacity:
            return read_val(self._capacity)
        else:
            return 0


    def plugged_in(self,):
        "Is the computer plugged in?"
        if self._plugged:
            return bool(read_val(self._plugged))
        else:
            # Fake answer if can't determine state
            return True

    def status(self,):
        print("Lid open:", self.lid_open())
        print("Plugged in:", self.plugged_in())
        print("Batt Capacity:", self.get_capacity())


if __name__ == "__main__":
    Computer().status()
