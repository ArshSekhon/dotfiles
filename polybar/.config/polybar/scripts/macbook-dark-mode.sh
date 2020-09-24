#!/bin/sh
echo "1" > /sys/class/leds/smc::kbd_backlight/brightness
echo "30" > /sys/class/backlight/intel_backlight/brightness
