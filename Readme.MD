Using Cron is nice if you have a server or never turn off your computer, but what if your laptop is asleep during the exact minute you have set to run your script? What if you have to reboot? What if your computer is actually running, but you would rather wait until its idle with the lid closed before running a backup process or other intensive script?

With LazyCron, "Your computer will get around to it eventually." LazyCron takes a more lackadaisical approach to life. Sure it will get the job done, but there's no rush. You don't set a time to run, you set a range. In schedule.txt, "Time" is the window is when the script is allowed to run. You can have multiple time windows separated with commas. For example: 1-3am, 2pm-4pm, 11:30-11:34 - Play around with these numbers, the system is very flexible. When you run my script, it will show you the next time window available for each program so you can confirm it's doing what you expected.

You can also set various requirements like the computer must be idle for a certain amount of time, busy, plugged in, online, the lid closed and more. See full options in schedule.txt

Usage: Edit schedule.txt and run LazyCron.py

Type ./LazyCron.py -h for help and full list of options:

Bonus functionality:

	--idle will put the computer to sleep after so many minutes. If plugged in, it will check first to make sure you don't have any disk or network activity. I find this more useful than using the default sleep timer which will put the computer to sleep regardless of what's going on like in the middle of a long slow file download or file copy operation.

====

Requirements:

	* xprintidle to get the idle time
	* systat package to get iostat which is used to measure disk activity before putting computer to sleep.
