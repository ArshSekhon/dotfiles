#!/bin/sh
player_status=$(playerctl status 2> /dev/null)
if [ "$player_status" = "Playing" ] || [ "$player_status" = "Paused" ]; then

	zscroll -b " ♪ " -d 0.1 -l 30 \
		-M "playerctl status" \
		-m "Playing" "-b '♪ '" \
		-m "Stopped" "" \
		-m "Paused" "-b '♪ ' --scroll 0" \
		-u t "playerctl metadata title" \
        	-l 20	&
fi
wait
