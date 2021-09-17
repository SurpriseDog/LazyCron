Using Cron is nice if you have a server or never turn off your computer, but what if your laptop is asleep during the exact minute you have set to run your script? What if you have to reboot? What if your computer is actually running, but you would rather wait until its idle with the lid closed before running a backup process or other intensive script?

With LazyCron, "Your computer will get around to it eventually." LazyCron takes a more lackadaisical approach to life. Sure it will get the job done, but there's no rush. You don't set a time to run, you set a range.

In schedule.txt, "Time" is the window is when the script is allowed to run. You can have multiple time windows separated with commas. For example: `1-3am, 2pm-4pm, 11:30-11:34` - Play around with these numbers, the system is very flexible. When you run my script, it will show you the next time window available for each program so you can confirm it's doing what you expected.

You can also set various requirements like the computer must be idle for a certain amount of time, busy, plugged in, online, the lid closed and more. See full options in schedule.txt

----

# Schedule.txt

You edit your schedule.txt file with programs to run:

### Example:

```

#Time              Frequency     Date              Requirements           Script Path
2pm-8pm            *             *                 online                 a_daily_script.py
8:30pm-3am         1h            sat-sun           idle 5m, plugged       backup_script_path_goes_here.sh
-5pm               *             m-f               random 8h              A_surprise_everyday.py
4-6pm              *             2nd Thursday      *                      mpg123 'Libera - Going Home.mp3'
*                  *             March 14          *                      pi_day.py
*                  *             1st-2nd           *                      zenity --info --text="Monthly list"
*                  *             *                 start 1                run_at_startup.sh

```

  * **"Time"** is the window is when the script is allowed to run. You can have multiple windows separated with commas.
Example: 1-3am, 2pm-4m, 11:30-11:34 - Play around with these numbers, the system is very flexible. When you run my script it will show you the next time window available for each program.

  * **"Frequency"** is how often the program. m = minutes, h = hours and so on. My script should allow most natural language inputs here. Time towards frequency is only counted when the computer is actively in use. Set as * and it will only run once a day.

  * **"Date"** field is usually set as a range to limit it to run on certain days of the week:
Example: m-f, every 2nd Thursday

Use * for fields that you don't need to fill in.

### Requirements is a comma separated list of additional requirements needed for the script to run. Available ones are as follows:

  *    idle    = Time the computer has been idle for
  *    busy    = Computer must have been in use within time specified
  *    plugged = Power cord must be attached
  *    closed  = Lid must be closed
  *    start   = Only run this many times at startup. 0 = infinite
  *    elapsed = Computer must be used for a certain amount of time in day before running.
  *    online  = Do we have internet access?
  *    random  = Script will run randomly. Example: random 8h will (on average) run every 8 hours. Some days it will run 3+ times, other days not at all.

----


# Bonus functionality:

	--idle will put the computer to sleep after so many minutes. If plugged in, it will check first to make sure you don't have any disk or network activity. I find this more useful than using the default sleep timer which will put the computer to sleep regardless of what's going on like in the middle of a long slow file download or file copy operation.


# Requirements:

  * xprintidle to get the idle time
  * systat package to get iostat which is used to measure disk activity before putting computer to sleep.

	You can get these in by typing:

```
	sudo apt install xprintidle sysstat
```

# Usage:

 * Edit schedule.txt with your own personal programs.
 * Run ./LazyCron.py
 * Type ./LazyCron.py -h for help and full list of options:

Not sure if your schedule will work correctly? Run the program with the --testing option or just put a # before each script path to show what it would do.
