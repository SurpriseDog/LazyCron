Using Cron is nice if you have a server or never turn off your computer, but what if your laptop is asleep during the exact minute you have set to run your script? What if you have to reboot? What if your computer is actually running, but you would rather wait until it's idle with the lid closed before running a backup process or other intensive script?

With LazyCron, "Your computer will get around to it eventually." LazyCron takes a more lackadaisical approach to life. Sure, it will get the job done, but there's no rush. You don't set a time to run, you set a range. Better yet, whenever scripts run and encounter an error, LC will pop up a message to let you know something went wrong instead of just failing silently.

----

## Schedule.txt

You edit your schedule.txt file with programs to run:

"Time" is the window is when the script is allowed to run. You can have multiple time windows separated with commas. For example: `1-3am, 2pm-4pm, 11:30-11:34` - Play around with these numbers; the system is very flexible. When you run my script, it will show you the next time window available for each program so you can confirm it's doing what you expected.

For example, let’s say you have a backup script that you only want to run when the computer is online, but not otherwise in use. In `schedule.txt` below I set the time range to between 8:30pm and 3am. The frequency is set to `*` which means it will only run once during that time period. The date is set to `sat-sun` meaning it will only run on Saturdays and Sundays. The requirements field says that the computer must be idle for at least 5 minutes, plugged in and online. Otherwise the script will wait until those conditions are met.

You can also set various requirements, such as: the computer must be idle for a certain amount of time, busy, plugged in, online, the lid must be closed and more. See full options below in the [Requirements](# Requirements) section.

### Example:

```

#Time              Frequency     Date              Requirements                   Script Path
8:30pm-3am         *             sat-sun           idle 5m, plugged, online        daily_backup_script_path_goes_here.sh
*                  1h            *                 busy 10, idle 5                my_hourly_backup_script.py
2pm-8pm            1h elapsed    *                 online                         a_daily_script.py
-5pm               *             m-f               random 8h                      A_surprise_everyday.py
4-6pm              *             2nd Thursday      busy 5m                        mpg123 'Libera - Going Home.mp3'
*                  *             March 14          *                              pi_day.py
*                  *             1st-2nd           *                              zenity --info --text="Monthly todo"
*                  *             *                 start 1                        run_at_startup.sh

```


### Time

Window when the script is allowed to run.

     - `1-3am, 2pm - 4pm` (You can have multiple windows separated with commas.)
     - `-5pm` will run until 5pm everyday
     - A `*` will run 24 hours a day.
     Play around with these numbers, the system is very flexible. When you run my script it will show you the next time window available for each program.


### Frequency

How often the program runs. m = minutes, h = hours and so on. My script should allow most natural language inputs here.

    - 1h will run every hour
    - 1h elapsed will only count time when the computer is actively in use by user.
	- A `0` will run as often as possible.
    - A `*` will only run once a day.

### Date

Usually set as a range to limit it to run on certain days of the week:
Examples: m-f, every 2nd Thursday

    - `m-f` will run monday through friday
    - `2nd Thursday` will run every 2nd thursday of the month
    - `1-2nd` will run on the first two days of the month
    - A `*` will run on any day of the year.



### Requirements
 A comma separated list of additional requirements needed for the script to run. As with Time, Frequency, and Date, most natural language inputs are allowed. Available ones are as follows:

| | |
| :---   | :--- |
| **Time Requirements** |    |
| | |
| `idle` | Time the computer has been idle for. |
| `busy` | Time the computer has been continuously busy for |
| `elapsed` | Total time computer must be used for. |
| `today` |  Total time today the computer must be used for. |
| | |
| | |
| **Computer State Requirements** | |
| | |
| `online` | Do we have internet access? |
| `closed/open` | Lid must be closed. |
| `(un)plugged` | Power cord must be attached. |
| `lowbatt` | Run if the battery percentage falls below a certain percentage. |
| `minbatt` | Run if the battery percentage is above a certain percentage. |
| `disk` | Maximum current disk usage to start process, expressed in KB/s |
| `cpu` | Maximum current cpu usage to start process, expressed as a percentage of combined cpu power. |
| `network` | Maximum current network usage to start process, expressed as KB/s |
| `ssid` | Check to see if the wifi network name matches before running. |
| | |
| | |
| **When and How often** | |
| | |
| `start` | Only run this many times at startup. 0 = infinite |
| `skip` | Skip running this process x times at startup. |
| `max` | Maximum number of times to run a script. |
| `reps` | Only run so many times per day or per window of time. |
| `delay` | Delay before starting script |
| `suspend` | Run script on suspend (if trigged by script with --idle option) |
| `wake` | Run script on wake after suspend |
| `random` | Script will run randomly <br /> Example: random 8h will (on average) run every 8 hours.<br />Some days it might run 5+ times, other days not at all. <br />That's how [randomness works.](https://math.stackexchange.com/q/209987/693067) |
| | |
| | |
| **Loops** | |
| | |
| `loop` | Run script this many times when the script ends. loop 0 = loop forever. Does not count toward reps. |
| `retry` | Retry this many times on failure. Does not count toward reps. |
| `loopdelay` | Delay this long after loop or retry. Default = 60 seconds if not set. |
| `delaymult` | Multiply delay after each loop. Default to 2 (double delay every loop in retry mode) |
| | |
| | |
| **Environment** | |
| | |
| `nice` | Start script with unix nice value. Higher values are nicer to other processes |
| `nologs` | Delete logs if script returns code `0` (all okay) |
| `localdir` | Run a script from the same directory that it's in. |
| `timeout` | Time to allow the script to run before killing it. |
| `environs` | Set environmental variables before starting.  <br /> Format : `environs VAL1=TEXT $ VAL2=TEXT` (seperate variables with $) |
| `shell` | Sets `subprocess.run(shell=True)` <br /> Allows access to advanced shell features in command, but is considered a [security risk.](https://docs.python.org/3/library/subprocess.html#security-considerations) |




**Reminder**: Use `*` for fields that you don't need to fill in. All 5 fields must contain at least 1 character.


----


## Installation:

`xprintidle` is required to get the number of seconds computer has been idle.

To use the system monitoring utilities for the `cpu`, `network` or `disk` flags; please install `psutil` with: `python3 -m pip install psutil`



## Usage:

 * Edit schedule.txt with your own personal programs.
 * Run ./LazyCron.py
 * Type ./LazyCron.py -h for help and full list of options

Not sure if your schedule will work correctly? Run the program with the --testing option or just put a `##` before each script path to show what it would do. Logs are kept in /tmp/LazyCron_logs

## Smart suspend management:

`--idle (minutes)` - Go to sleep after so many minutes while plugged in.
`--idlebatt (minutes)` - Go to sleep after so many minutes on battery power.

  * It will check first to make sure you don't have any disk or network activity. - I find this more useful than using the default sleep timer, which will put the computer to sleep regardless of what's going on (e.g. it's in the middle of a long, slow file download or file copy operation).
  * Add programs with `suspend` option to the `Requirements` list in order to run them on before suspend. - LC will wait 1 cycle after running a suspend program before putting the computer to sleep. If the computer shows activity in this period, the sleep will be cancelled.

## Troubleshooting:

**My scripts only run once a day!**

  * Make sure the Frequency field has a `0` in it not a `*`

**How do I get messages on the desktop if a program fails?**


  * Install PyQt6 python module from pip (preferred): `sudo pip install PyQt6`

  * or install the third party app: `zenity` `sudo apt install zenity`

**What does the list of numbers mean everytime a program is started in `--verbose = 2 mode?`**

  * It's a history of runtimes. Instead of recording the unix timestamp, I found it more compact to record the number seconds since the log started.

  * Add these numbers to the timestamp at the start of the log to get an exact [unix timestamp](https://en.wikipedia.org/wiki/Unix_time) of when each program started.


## Future:

Ideas that could be implemented in the future. File a bug report if with the tag "proposal" if this or another idea interests you:

  * Boolean logic for requirements: `idle 2m OR today 3h`
     - Currently all requirements run as `AND`.


  * Mac / Windows Support

  * New requirement fields, let me know what you want to see!
