#!/system/bin/sh
set -eu
DIR=/data/local/tmp/maxwave
[ "$(cat "$DIR/owner")" = maxwave-v1 ] || exit 2
if [ -f "$DIR/server.pid" ]; then
 old=$(cat "$DIR/server.pid")
 case "$old" in ''|*[!0-9]*) exit 3;; esac
 if kill -0 "$old" 2>/dev/null; then
  [ "$(readlink "/proc/$old/exe")" = "$DIR/frida-server" ] || exit 4
  echo "MaxWave server already running: $old"
  exit 0
 fi
fi
. "$DIR/env.sh"
"$DIR/frida-server" --policy-softener=internal --listen 127.0.0.1:27043 --ignore-crashes > "$DIR/server.log" 2>&1 &
pid=$!
echo "$pid" > "$DIR/server.pid"
echo "MaxWave server: $pid (loopback only)"
