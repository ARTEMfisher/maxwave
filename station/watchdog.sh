#!/system/bin/sh
set -u
D=/data/local/tmp/maxwave-native
if ! mkdir "$D/watchdog.lock" 2>/dev/null; then
 p=$(cat "$D/watchdog.pid" 2>/dev/null || true)
 case "$p" in ''|*[!0-9]*) ;; *)
  if [ -r /proc/$p/cmdline ] && tr '\000' ' ' < /proc/$p/cmdline | grep -F "$D/watchdog.sh" >/dev/null; then exit 0; fi;;
 esac
 rmdir "$D/watchdog.lock" 2>/dev/null || exit 1
 mkdir "$D/watchdog.lock" 2>/dev/null || exit 1
fi
echo $$ > "$D/watchdog.pid"
child=''
cleanup(){
 if [ -n "$child" ] && [ "$(readlink /proc/$child/exe 2>/dev/null || true)" = "$D/maxwaved" ]; then kill -TERM "$child" 2>/dev/null; fi
 rm -f "$D/watchdog.pid"
 rmdir "$D/watchdog.lock" 2>/dev/null || true
}
trap 'cleanup; exit 0' TERM INT
trap cleanup EXIT
. "$D/env.sh"
while [ -f "$D/enabled" ] && [ ! -f "$D/disabled" ]; do
 if [ -f "$D/daemon.log" ] && [ "$(wc -c < "$D/daemon.log")" -gt 3145728 ]; then mv -f "$D/daemon.log" "$D/daemon.log.1"; fi
 "$D/maxwaved" >> "$D/daemon.log" 2>&1 &
 child=$!
 wait "$child"
 child=''
 [ -f "$D/disabled" ] && break
 sleep 5
done
