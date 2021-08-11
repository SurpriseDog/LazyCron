#!/usr/bin/python3
# LazyCron - "Your computer will get around to it eventually."
# Usage: Run with -h for help.

################################################################################

import os
import sys
import time

import how_busy
import scheduler

from sd.common import itercount, gohome, quickrun, check_install, shell, rint, tman, rfs, msgbox

import sd.chronology as chronos
from sd.arg_master import easy_parse
from window_watch import WindowWatch		# nocommit

def parse_args():
	"Parse arguments"
	positionals = [\
	["schedule", '', str, 'schedule.txt'],
	"Filename to read schedule from."
	]
	args = [\
	['polling', 'polling_rate', float, 1],
	"How often to check (minutes)",
	['idle', '', float, 0],
	"How long to wait before going to sleep (minutes) 0=Disable",
	['verbose', '', int, 1],
	"What messages to print",
	['testing', '', bool],
	"Do everything, but actually run the scripts.",
	['skip', '', bool],
	"Don't run apps on startup, wait a bit.",
	['stagger', '', float, 0],
	"Wait x minutes between starting programs.",
	]
	return easy_parse(args,
					  positionals,
					  usage='<schedule file>, options...',
					  description='Monitor the system for idle states and run scripts at the best time.')


def is_busy(min_net=10e3, min_disk=1e6):
	'''
	Return True if disk or network usage above defaults
	min_net  = Network usage
	min_disk = Disk usage
	'''
	def fmt(num):
		return rfs(num)+'/s'

	net_usage = how_busy.get_network_usage(5, 4)
	if net_usage >= min_net:
		print("Network Usage:", fmt(net_usage))
		return True

	disk_usage = how_busy.all_disk_usage(5, 4)
	if disk_usage >= min_disk:
		print("Disk usage:", fmt(disk_usage))
		return True

	print("Network Usage:", fmt(net_usage), end=' ')
	print("Disk usage:", fmt(disk_usage))
	return False



def main(args):
	polling_rate = args.polling_rate * 60	 # Time to rest at the end of every loop
	idle_sleep = args.idle * 60
	if idle_sleep:
		check_install('iostat', 'sar',
					  msg='''sudo apt install sysstat sar
					  --idle requires iostat () to determine if the computer can be put to sleep.''')
	check_install('xprintidle', msg="sudo apt install xprintidle")

	schedule_file = args.schedule	# Tab seperated input file
	testing_mode = args.testing		# Don't actually do anything

	idle = 0                    # Seconds without user inteaction.
	elapsed = 0                 # Total time Computer has spent not idle
	total_idle = 0
	last_idle = 0
	timestamp = time.time()     # Timestamp at start of loop
	last_schedule_read = 0      # last time the schedule file was read
	last_run = 0				# Time when the last program was started
	schedule_apps = []
	cur_day = time.strftime('%d')
	ww = WindowWatch(schedule_file)			# nocommit
	for counter in itercount():
		# Sleep at the end of every loop
		if counter:
			missing = chronos.msleep(polling_rate)
			if missing:
				if missing > 5:
					print("Unaccounted for time during sleep:", chronos.fmt_time(missing))
				# Loop again to avoid edge case where the machine wakes up and is immediately put back to sleep
				total_idle = float(shell('xprintidle')) / 1000
				timestamp = time.time()
				continue

			# Get idle time and calculate elapsed time
			last_idle = total_idle
			total_idle = float(shell('xprintidle')) / 1000

			if total_idle > last_idle:
				idle = total_idle - last_idle
			else:
				idle = total_idle
			new_time = time.time()
			elapsed += new_time - timestamp - idle
			if counter == 1:
				elapsed = 0
			timestamp = new_time
			if args.verbose >= 2:   # not (counter - 1) % 10:
				print(chronos.local_time(), 'Elapsed:', chronos.fmt_time(elapsed), 'Idle:', rint(total_idle))

			# Check for a new day
			if time.strftime('%d') != cur_day:
				elapsed = 0
				cur_day = time.strftime('%d')
				print(time.strftime('\n\nToday is %A, %-m-%d'))
				print('#'*80)

		ww.check(polling_rate - idle)								# nocommit
		#if polling_rate < 60 and counter % (60 // polling_rate): 	# nocommit
		#	continue											 	# nocommit

		# Read the schedule file if it's been updated
		if os.path.getmtime(schedule_file) > last_schedule_read:
			if counter:
				print("\n\nSchedule file updated:")
			last_schedule_read = time.time()
			try:
				schedule_apps = scheduler.read_schedule(schedule_apps, schedule_file)
			except RuntimeError:
				if counter:
					msgbox("Error reading:", schedule_file)
				else:
					sys.exit(1)


		# Run scripts if enough elapsed time has passed
		for proc in schedule_apps:
			if args.stagger and (time.time() - last_run) / 60 < args.stagger:
				break
			if proc.in_window() and proc.next_elapsed <= elapsed:
				if args.skip and counter < 8:
					testing = True
				else:
					testing = testing_mode
				if proc.run(elapsed=elapsed, idle=total_idle, polling_rate=polling_rate, testing_mode=testing):
					last_run = time.time()


		# Put the computer to sleep after checking to make sure nothing is going on.
		if idle_sleep and total_idle > idle_sleep:
			if scheduler.is_plugged():
				# Plugged mode waits for idle system.
				ready, results = tman.query(is_busy, max_age=polling_rate * 1.5)
				if ready:
					if not results:
						print("Going to sleep\n")
						if not testing_mode:
							quickrun('systemctl', 'suspend')
			else:
				# Battery Mode doesn't wait for idle system.
				print("Idle and unplugged. Going to sleep.")
				if not testing_mode:
					quickrun('systemctl', 'suspend')




if __name__ == "__main__":
	UA = parse_args()
	# Min level to print messages:
	scheduler.EP.verbose = 1 - UA.verbose
	gohome()
	main(UA)
