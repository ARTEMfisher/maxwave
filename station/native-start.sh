#!/system/bin/sh
set -eu
D=/data/local/tmp/maxwave-native
[ -x "$D/maxwaved" ] && [ -f "$D/env.sh" ] && [ -r "$D/token" ]
touch "$D/enabled"
rm -f "$D/disabled"
nohup /system/bin/sh "$D/watchdog.sh" </dev/null >/dev/null 2>&1 &
echo 'Station service start requested'
