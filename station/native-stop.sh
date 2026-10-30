#!/system/bin/sh
set -eu
D=/data/local/tmp/maxwave-native
# Disable future starts first. Only terminate executables owned by this installation.
rm -f "$D/enabled"
touch "$D/disabled"
for f in watchdog.pid daemon.pid; do
 [ -f "$D/$f" ] || continue
 p=$(cat "$D/$f")
 case "$p" in ''|*[!0-9]*) continue;; esac
 if [ "$f" = daemon.pid ]; then
  [ "$(readlink /proc/$p/exe 2>/dev/null || true)" = "$D/maxwaved" ] || continue
 else
  tr '\000' ' ' < /proc/$p/cmdline 2>/dev/null | grep -F "$D/watchdog.sh" >/dev/null || continue
 fi
 kill -TERM "$p" 2>/dev/null || true
done
for p in $(pidof frida-inject 2>/dev/null || true); do
 [ "$(readlink /proc/$p/exe 2>/dev/null || true)" = "$D/frida-inject" ] || continue
 kill -TERM "$p" 2>/dev/null || true
done

if [ -f "$D/daemon.pid" ]; then
 p=$(cat "$D/daemon.pid")
 case "$p" in ''|*[!0-9]*) rm -f "$D/daemon.pid";; *)
  [ "$(readlink /proc/$p/exe 2>/dev/null || true)" = "$D/maxwaved" ] || rm -f "$D/daemon.pid";;
 esac
fi
