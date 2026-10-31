#!/system/bin/sh

D=/data/local/tmp/maxwave-native
PKG=app.rvx.android.apps.youtube.music
ACTIVITY=com.google.android.apps.youtube.music.activities.MusicActivity
LOG="$D/youtube-music-autostart.log"
MARKER="$D/youtube-music.bootid"
LOCK="$D/youtube-music.lock"

log() {
    echo "$(date '+%F %T') $*" >> "$LOG"
}

if ! mkdir "$LOCK" 2>/dev/null; then
    exit 0
fi

trap 'rmdir "$LOCK" 2>/dev/null' EXIT
trap 'exit 0' TERM INT

sleep 30

BOOT_ID=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null)
[ -n "$BOOT_ID" ] || BOOT_ID=unknown

if [ -f "$MARKER" ] && [ "$(cat "$MARKER" 2>/dev/null)" = "$BOOT_ID" ]; then
    log "Already processed this boot; exiting"
    exit 0
fi

echo "$BOOT_ID" > "$MARKER"
log "YouTube Music autostart started; boot_id=$BOOT_ID"

if ! pm path "$PKG" >/dev/null 2>&1; then
    log "ERROR: package not installed: $PKG"
    exit 1
fi

PID=$(pidof "$PKG" 2>/dev/null || true)

if [ -n "$PID" ]; then
    log "YouTube Music process already running; pid=$PID"
else
    log "YouTube Music process not found"
fi

if dumpsys activity activities 2>/dev/null | grep -E 'mResumedActivity|ResumedActivity' | grep -F "$ACTIVITY" >/dev/null; then
    log "MusicActivity is already resumed"
else
    log "MusicActivity is not resumed; launching"
    /system/bin/am start -n "$PKG/$ACTIVITY" >> "$LOG" 2>&1
fi

i=0
while [ "$i" -lt 24 ]; do
    PID=$(pidof "$PKG" 2>/dev/null || true)
    [ -n "$PID" ] && break
    sleep 5
    i=$((i + 1))
done

if [ -z "$PID" ]; then
    log "ERROR: YouTube Music process did not appear"
    exit 1
fi

log "YouTube Music process running; pid=$PID"

i=0
while [ "$i" -lt 24 ]; do
    if dumpsys activity activities 2>/dev/null | grep -E 'mResumedActivity|ResumedActivity' | grep -F "$ACTIVITY" >/dev/null; then
        log "MusicActivity successfully resumed"
        break
    fi
    sleep 5
    i=$((i + 1))
done

if [ "$i" -ge 24 ]; then
    log "WARNING: MusicActivity did not become resumed"
fi

i=0
while [ "$i" -lt 24 ]; do
    if dumpsys media_session 2>/dev/null | grep -F "$PKG" >/dev/null; then
        log "MediaSession detected"
        exit 0
    fi
    sleep 5
    i=$((i + 1))
done

log "WARNING: MediaSession was not detected"
exit 0
