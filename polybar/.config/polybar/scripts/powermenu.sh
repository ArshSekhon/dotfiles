#!/bin/bash
choices="Logout\nShutdown\nReboot\nCancel"
chosen=$(echo -e $choices | rofi -dmenu -theme "~/.config/rofi/shtdwn.rasi" -i -p "Power Menu" ) #-location 4 -width -20)
echo "$chosen"

case "$chosen" in
		Logout) i3-msg exit || openbox --exit ;;
		Shutdown) poweroff ;;
		Reboot) reboot ;; 
		Cancel) ignore;;
esac
