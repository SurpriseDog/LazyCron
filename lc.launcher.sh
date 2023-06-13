#!/bin/bash
# Launch LazyCron from a limited environment like crontab




ARGS="$*"
cd `dirname "$0"`


# Wait
if [[ `sed 's/ .*//;s/\..*//' /proc/uptime` -lt 64 ]]; then
	echo "Sleeping at boot to be nice"
	sleep 8
fi


# Setup Logging
LOGS="/tmp/LazyCron_logs/lc.launcher.logs.$USER.txt"
mkdir -p /tmp/LazyCron_logs/
truncate -s 0 "$LOGS"
elog(){ echo -e "ELOG $*"; echo -e "ELOG $*" >> "$LOGS"; }


# Choose correct display
DISPLAY=$(w | grep `whoami` | awk '{print $3}')
if [[ -z "$DISPLAY" ]]; then
	elog "Unable to find Display, defaulting to 0"
	DISPLAY=:0
fi
export DISPLAY=$DISPLAY


# Setup Path
export PATH=`sed 's/PATH=//' /etc/environment`


# Log status
elog "Time = `date +%H:%M:%S`"
elog "Current directory: $PWD"
elog "Current user: $USER"
elog "Display = $DISPLAY"
elog "Path = $PATH"
elog "Logs = $LOGS"
elog "Arguments = $ARGS"
elog "Currently logged in:"
w >> "$LOGS"




# Run Program
elog "\n\n\n"
if [[ -z `whereis zenity` ]]; then
	elog "Install zenity to get desktop notifications if LC crashes."
	python3 -u ./LazyCron.py $ARGS >> "$LOGS" 2>&1
else
	python3 -u ./LazyCron.py $ARGS >> "$LOGS" 2>&1 || zenity --info "info" --timeout=99999999 --text="LazyCron error at `date +%H:%M`"
fi
