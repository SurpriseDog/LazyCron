#!/usr/bin/python3

import os
from sd.bash import quickrun
from sd.read_state import read_state
from sd.common import read_val, read_file, warn


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
        lid = "/proc/acpi/button/lid/LID0/state"
        if not os.path.exists(lid):
            print("Cannot find file to access lid state")
            self.lid_state = None
        else:
            self.lid_state = lid

        # Battery capacity
        for cname, mname in [['charge_now', 'charge_full'], ['energy_now', 'energy_full']]:
            self.batt_capacity = get_filename(cname)
            if self.batt_capacity:
                self.max_power = int(read_file(get_filename(mname)))
                break
        else:
            self.batt_capacity = get_filename('capacity')
            self.max_power = 100
        if not self.batt_capacity:
            print("Cannot find file to access battery state")
        else:
            if verbose:
                print("Using battery capacity file:", self.batt_capacity)
            self.batt_capacity = open(self.batt_capacity)

        if not self.batt_capacity or not self.lid_state:
            print("Disregard these messages if you are running on a laptop system.")


    def lid_open(self,):
        if self.lid_state:
            return read_state(self.lid_state).split()[1] == "open"
        else:
            # Fake answer if can't determine state
            return True

    def get_capacity(self,):
        "Battery max charge"
        if self.batt_capacity:
            return read_val(self.batt_capacity)
        else:
            return 100

    def get_charge(self,):
        "Battery percent left returned as percent x 100"
        return self.get_capacity() / self.max_power * 100

    def get_ssid(self,):
        "Current Wifi Network"
        ssid = quickrun('iwgetid', '-r', hidewarning=True, check=False)
        if ssid:
            return ssid[0].strip()
        else:
            return ""


    def plugged_in(self,):
        "Is the computer plugged in?"
        if self._plugged:
            return bool(read_val(self._plugged))
        else:
            # Fake answer if can't determine state
            return True

    def status(self,):
        "Testing all functions"
        print("Lid open:", self.lid_open())
        print("Plugged in:", self.plugged_in())
        print("Battery Capacity:", self.get_capacity())
        print("Battery Max Power:", self.max_power)
        print("Charge:", int(self.get_charge()))
        print("SSID:", self.get_ssid())


if __name__ == "__main__":
    Computer().status()
