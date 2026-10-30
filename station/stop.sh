#!/system/bin/sh
set -eu
DIR=/data/local/tmp/maxwave
[ "$(cat "$DIR/owner")" = maxwave-v1 ] || exit 2
[ -f "$DIR/server.pid" ] || exit 0
pid=$(cat "$DIR/server.pid")
case "$pid" in ''|*[!0-9]*) exit 3;; esac
if kill -0 "$pid" 2>/dev/null; then
 [ "$(readlink "/proc/$pid/exe")" = "$DIR/frida-server" ] || exit 4
 kill "$pid"
 echo "MaxWave server stopped"
fi
