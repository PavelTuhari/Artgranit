#!/bin/bash
# t° физического CPU по coretemp (lm-sensors sysfs). $1 = 1|2 (номер CPU).
# Возвращает максимум по всем датчикам пакета в целых °C. Не требует root.
# Ставится на cloudbd для zabbix-агента: docs/TBControl/CLOUDBD_TEMP_MONITOR.md
idx=$(( ${1:-1} - 1 ))
mapfile -t HW < <(for h in /sys/class/hwmon/hwmon*; do
  [ "$(cat "$h/name" 2>/dev/null)" = coretemp ] && echo "$h"
done | sort)
h="${HW[$idx]}"
[ -z "$h" ] && { echo 0; exit 0; }
max=0
for f in "$h"/temp*_input; do
  v=$(cat "$f" 2>/dev/null) || continue
  [ "$v" -gt "$max" ] 2>/dev/null && max=$v
done
echo $(( max / 1000 ))
