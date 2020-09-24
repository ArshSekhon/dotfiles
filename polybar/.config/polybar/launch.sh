#!/bin/bash

# Terminate already running bar instances
killall -q polybar

# Wait until the processes have been shut down
while pgrep -u $UID -x polybar >/dev/null; do sleep 1; done


if type "xrandr"; then
  for m in $(xrandr --query | grep " connected" | cut -d" " -f1); do
    MONITOR=$m polybar -rq bar-top &
    MONITOR=$m polybar -rq bar-bottom &
  done
else
  polybar -rq bar-top &
  polybar -rq bar-bottom &
fi

echo "Polybar launched..."
