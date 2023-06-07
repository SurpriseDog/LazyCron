#!/bin/bash
# Launch LazyCron from a limited environment like crontab


ARGS="$*"
cd `dirname "$0"`



# Setup Logging
LOGS="/tmp/lazycron_logs.txt"
truncate -s 0 $LOGS
elog(){ echo "ELOG $*"; echo "ELOG $*" >> "$LOGS"; }


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



# Wait
elog "Sleeping at boot to be nice"
sleep 8




# Run Program
elog ""
elog ""
if [[ -z `whereis zenity` ]]; then
	elog "Install zenity to get desktop notifications if LC crashes."
	./LazyCron.py $ARGS >> "$LOGS" 2>&1
else
	./LazyCron.py $ARGS >> "$LOGS" 2>&1 || zenity --info "info" --timeout=99999999 --text="LazyCron error at `date +%H:%M`"
fi
