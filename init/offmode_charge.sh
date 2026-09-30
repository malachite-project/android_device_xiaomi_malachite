#!/vendor/bin/sh
#
# Started by init.mt6878.rc on the charging screen (off-mode charging) only.
#
# Arm Xiaomi's power_off_mode flag again, so that unplugging from the charging
# screen and plugging in later shows the charging screen again instead of
# booting Android. The bootloader writes the flag back to 2 on every boot, and
# the kernel writes 2 again once it can reach the charger partition, about
# 58 s after boot; until then the node reads 0 and writes fail. With the flag
# at 1 the bootloader still boots Android for the power key or a restart, so
# holding power on the charging screen keeps working.
#
# Only shell builtins and the vendor toybox: init's PATH lists /system/bin
# first, which a vendor domain may not execute.

node=/sys/class/power_supply/battery/charger_partition_poweroffmode

/vendor/bin/sleep 30
tries=0
while [ "$tries" -lt 60 ]; do
  tries=$((tries + 1))
  value=
  read -r value < "$node"
  if [ "$value" = 1 ] || [ "$value" = 2 ]; then
    # Ready. The kernel's own reset follows within a millisecond; wait it
    # out, write, and stop only if the value is still 1 a while later.
    /vendor/bin/sleep 2
    echo 1 > "$node"
    /vendor/bin/sleep 5
    value=
    read -r value < "$node"
    if [ "$value" = 1 ]; then
      exit 0
    fi
  fi
  /vendor/bin/sleep 3
done
exit 1
