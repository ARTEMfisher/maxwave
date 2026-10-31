"""Optional SSH management for stations with an SSH server already configured.

SSH is only a management transport. Installation, APK transfers and scrcpy
continue to use ADB. This module never installs or configures an SSH server,
root method, boot service, init hook, SELinux policy or firewall rule.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import pathlib
import re
import shutil
import subprocess

from .common import ROOT, STATE, UserError, menu as show_menu, save_config

OWNER_MARKER = "maxwave-station-native-v1"

STATUS_SCRIPT = r"""set -eu
D=/data/local/tmp/maxwave-native
owner=$(cat "$D/owner" 2>/dev/null || true)
[ "$owner" = "maxwave-station-native-v1" ] || {
    echo "ERROR: MaxWave installation marker not found" >&2
    exit 20
}
echo "MaxWave installation: found"
if [ -f "$D/enabled" ] && [ ! -f "$D/disabled" ]; then
    echo "Service flag: enabled"
else
    echo "Service flag: disabled"
fi
if grep -F '# BEGIN MaxWave autonomous' /data/local/tmp/myscript-max.sh >/dev/null 2>&1; then
    echo "Boot hook: present"
else
    echo "Boot hook: not found"
fi
pid=$(cat "$D/daemon.pid" 2>/dev/null || true)
case "$pid" in
    '') echo "Daemon: stopped" ;;
    *[!0-9]*) echo "Daemon: invalid PID file" ;;
    *)
        if [ "$(readlink "/proc/$pid/exe" 2>/dev/null || true)" = "$D/maxwaved" ]; then
            echo "Daemon: running (pid=$pid)"
        else
            echo "Daemon: not running (stale PID file)"
        fi
        ;;
esac
pid=$(cat "$D/watchdog.pid" 2>/dev/null || true)
case "$pid" in
    '') echo "Watchdog: stopped" ;;
    *[!0-9]*) echo "Watchdog: invalid PID file" ;;
    *)
        cmd=$(tr '\000' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)
        case "$cmd" in
            *"$D/watchdog.sh"*) echo "Watchdog: running (pid=$pid)" ;;
            *) echo "Watchdog: not running (stale PID file)" ;;
        esac
        ;;
esac
"""

VALIDATE_SCRIPT = r"""set -eu
D=/data/local/tmp/maxwave-native
owner=$(cat "$D/owner" 2>/dev/null || true)
[ "$owner" = "maxwave-station-native-v1" ] || {
    echo "ERROR: MaxWave installation marker not found" >&2
    exit 20
}
bad=0
for f in start.sh stop.sh watchdog.sh env.sh token; do
    if [ -s "$D/$f" ]; then
        echo "$f: present"
    else
        echo "$f: MISSING"
        bad=1
    fi
done
for f in start.sh stop.sh watchdog.sh; do
    if [ -f "$D/$f" ]; then
        if /system/bin/sh -n "$D/$f"; then
            echo "$f: shell syntax OK"
        else
            echo "$f: shell syntax ERROR"
            bad=1
        fi
    fi
done
if [ -x "$D/maxwaved" ]; then
    echo "maxwaved: executable"
else
    echo "maxwaved: MISSING or not executable"
    bad=1
fi
token=$(cat "$D/token" 2>/dev/null || true)
case "$token" in
    ''|*[!0-9a-f]*)
        echo "IPC token: invalid or missing"
        bad=1
        ;;
    *)
        if [ "${#token}" -eq 64 ]; then
            echo "IPC token: length OK"
        else
            echo "IPC token: invalid length"
            bad=1
        fi
        ;;
esac
if grep -F '# BEGIN MaxWave autonomous' /data/local/tmp/myscript-max.sh >/dev/null 2>&1; then
    echo "Boot hook: present"
else
    echo "Boot hook: missing"
    bad=1
fi
[ "$bad" -eq 0 ] || exit 21
"""

BOOT_BACKUP_SCRIPT = r"""set -eu
D=/data/local/tmp/maxwave-native
owner=$(cat "$D/owner" 2>/dev/null || true)
[ "$owner" = "maxwave-station-native-v1" ] || {
    echo "ERROR: MaxWave installation marker not found" >&2
    exit 20
}
F=/data/local/tmp/myscript-max.sh
[ -s "$F" ] || {
    echo "ERROR: boot script is missing or empty" >&2
    exit 22
}
cat "$F"
"""

START_SCRIPT = r"""set -eu
D=/data/local/tmp/maxwave-native
owner=$(cat "$D/owner" 2>/dev/null || true)
[ "$owner" = "maxwave-station-native-v1" ] || {
    echo "ERROR: MaxWave installation marker not found" >&2
    exit 20
}
[ -f "$D/start.sh" ] || {
    echo "ERROR: MaxWave start script not found" >&2
    exit 21
}
/system/bin/sh "$D/start.sh"
i=0
while [ "$i" -lt 20 ]; do
    pid=$(cat "$D/daemon.pid" 2>/dev/null || true)
    case "$pid" in
        ''|*[!0-9]*) ;;
        *)
            if [ "$(readlink "/proc/$pid/exe" 2>/dev/null || true)" = "$D/maxwaved" ]; then
                echo "MaxWave started (pid=$pid)"
                exit 0
            fi
            ;;
    esac
    sleep 1
    i=$((i + 1))
done
echo "ERROR: MaxWave daemon did not start within 20 seconds" >&2
exit 22
"""

STOP_SCRIPT = r"""set -eu
D=/data/local/tmp/maxwave-native
owner=$(cat "$D/owner" 2>/dev/null || true)
[ "$owner" = "maxwave-station-native-v1" ] || {
    echo "ERROR: MaxWave installation marker not found" >&2
    exit 20
}
[ -f "$D/stop.sh" ] || {
    echo "ERROR: MaxWave stop script not found" >&2
    exit 21
}
/system/bin/sh "$D/stop.sh"
i=0
while [ -f "$D/watchdog.pid" ] || [ -f "$D/daemon.pid" ]; do
    if [ "$i" -ge 15 ]; then
        echo "ERROR: MaxWave did not stop within 15 seconds" >&2
        exit 22
    fi
    sleep 1
    i=$((i + 1))
done
echo "MaxWave stopped"
"""

RESTART_SCRIPT = r"""set -eu
D=/data/local/tmp/maxwave-native
owner=$(cat "$D/owner" 2>/dev/null || true)
[ "$owner" = "maxwave-station-native-v1" ] || {
    echo "ERROR: MaxWave installation marker not found" >&2
    exit 20
}
[ -f "$D/stop.sh" ] && [ -f "$D/start.sh" ] || {
    echo "ERROR: MaxWave control scripts are missing" >&2
    exit 21
}
/system/bin/sh "$D/stop.sh"
i=0
while [ -f "$D/watchdog.pid" ] || [ -f "$D/daemon.pid" ]; do
    if [ "$i" -ge 15 ]; then
        echo "ERROR: MaxWave did not stop within 15 seconds" >&2
        exit 22
    fi
    sleep 1
    i=$((i + 1))
done
/system/bin/sh "$D/start.sh"
i=0
while [ "$i" -lt 20 ]; do
    pid=$(cat "$D/daemon.pid" 2>/dev/null || true)
    case "$pid" in
        ''|*[!0-9]*) ;;
        *)
            if [ "$(readlink "/proc/$pid/exe" 2>/dev/null || true)" = "$D/maxwaved" ]; then
                echo "MaxWave restarted (pid=$pid)"
                exit 0
            fi
            ;;
    esac
    sleep 1
    i=$((i + 1))
done
echo "ERROR: MaxWave daemon did not restart within 20 seconds" >&2
exit 23
"""

LOG_SCRIPT = r"""set -eu
D=/data/local/tmp/maxwave-native
owner=$(cat "$D/owner" 2>/dev/null || true)
[ "$owner" = "maxwave-station-native-v1" ] || {
    echo "ERROR: MaxWave installation marker not found" >&2
    exit 20
}
for f in "$D/daemon.log.1" "$D/daemon.log"; do
    if [ -f "$f" ]; then
        echo "===== $f (last 50 lines) ====="
        tail -n 50 "$f"
    fi
done
"""


def validate_settings(settings):
    if not isinstance(settings, dict):
        raise UserError("SSH не настроен. Сначала задайте параметры подключения.")
    host = str(settings.get("host", "")).strip()
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?", host):
        raise UserError("Неверный SSH host. Укажите IPv4-адрес или DNS-имя без схемы и порта.")
    try:
        port = int(settings.get("port", 22))
    except (TypeError, ValueError):
        raise UserError("SSH port должен быть числом от 1 до 65535.")
    if not 1 <= port <= 65535:
        raise UserError("SSH port должен быть числом от 1 до 65535.")
    username = str(settings.get("username", "root")).strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,31}", username):
        raise UserError("Недопустимое имя SSH-пользователя.")
    identity_file = str(settings.get("identity_file", "") or "").strip()
    if identity_file:
        key_path = pathlib.Path(identity_file).expanduser()
        if key_path.suffix.lower() == ".pub":
            raise UserError("Укажите приватный ключ, а не файл .pub.")
        if key_path.suffix.lower() == ".ppk":
            raise UserError("Формат PuTTY .ppk не поддерживается OpenSSH. Используйте приватный ключ OpenSSH.")
        if not key_path.is_file():
            raise UserError("Файл приватного SSH-ключа не найден: " + str(key_path))
        identity_file = str(key_path.resolve())
    return {
        "host": host,
        "port": port,
        "username": username,
        "identity_file": identity_file,
    }


class SshClient:
    def __init__(self, cfg):
        self.settings = validate_settings(cfg.get("ssh"))
        configured = cfg.get("tools", {}).get("ssh")
        executable = None
        if configured:
            candidate = pathlib.Path(str(configured)).expanduser()
            if not candidate.is_absolute():
                candidate = ROOT / candidate
            if candidate.is_file():
                executable = str(candidate.resolve())
            else:
                executable = shutil.which(str(configured))
        else:
            executable = shutil.which("ssh")
        if not executable:
            raise UserError(
                "Не найден OpenSSH client (ssh). Установите компонент OpenSSH Client "
                "или добавьте ssh в PATH."
            )
        self.executable = executable

    def _command(self):
        settings = self.settings
        command = [
            self.executable,
            "-T",
            "-p", str(settings["port"]),
            "-o", "BatchMode=yes",
            "-o", "PreferredAuthentications=publickey",
            "-o", "PasswordAuthentication=no",
            "-o", "KbdInteractiveAuthentication=no",
            "-o", "StrictHostKeyChecking=yes",
            "-o", "ForwardAgent=no",
            "-o", "ClearAllForwardings=yes",
            "-o", "PermitLocalCommand=no",
            "-o", "ProxyCommand=none",
            "-o", "ProxyJump=none",
            "-o", "ControlMaster=no",
            "-o", "ControlPath=none",
            "-o", "ConnectTimeout=8",
            "-o", "ServerAliveInterval=5",
            "-o", "ServerAliveCountMax=2",
            "-o", "LogLevel=ERROR",
        ]
        if settings["identity_file"]:
            command.extend(["-i", settings["identity_file"], "-o", "IdentitiesOnly=yes"])
        else:
            command.extend(["-o", "IdentitiesOnly=no"])
        command.extend([
            f'{settings["username"]}@{settings["host"]}',
            "/system/bin/sh -s",
        ])
        return command

    def run(self, script, timeout=25, strip_output=True):
        if not isinstance(script, str) or "\x00" in script:
            raise UserError("SSH script должен быть текстом без NUL-байтов.")
        try:
            result = subprocess.run(
                self._command(),
                input=script,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise UserError(f"SSH-команда не завершилась за {timeout} секунд.")
        except OSError as exc:
            raise UserError("Не удалось запустить OpenSSH client: " + str(exc))
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()
            low = detail.lower()
            if "host key verification failed" in low or "remote host identification has changed" in low:
                raise UserError(
                    "OpenSSH не подтвердил host key станции. Проверьте fingerprint "
                    "и добавьте доверенный ключ станции в пользовательский known_hosts."
                )
            if "permission denied" in low:
                raise UserError(
                    "SSH-аутентификация отклонена. Проверьте пользователя, приватный ключ "
                    "и права на ключ. Вход по паролю отключён."
                )
            raise UserError("SSH-команда завершилась с ошибкой: " + (detail or f"код {result.returncode}"))
        return result.stdout if not strip_output else result.stdout.strip()

    def check_root(self):
        output = self.run("id -u\n", timeout=12).splitlines()
        uid = next((line.strip() for line in reversed(output) if line.strip()), "")
        if uid != "0":
            raise UserError(
                "SSH-соединение установлено, но удалённый пользователь не root "
                f"(uid={uid or 'не определён'}). Нужен уже настроенный root-доступ."
            )
        return uid


def _configure(cfg):
    current = cfg.get("ssh", {}) if isinstance(cfg.get("ssh"), dict) else {}
    target = str(cfg.get("target", ""))
    target_host = target.rsplit(":", 1)[0] if target.count(":") == 1 else target
    host = input(f"SSH host [{current.get('host') or target_host}]: ").strip() or current.get("host") or target_host
    port_text = input(f"SSH port [{current.get('port', 22)}]: ").strip() or str(current.get("port", 22))
    username = input(f"SSH user [{current.get('username', 'root')}]: ").strip() or current.get("username", "root")
    old_key = current.get("identity_file", "")
    key_prompt = old_key if old_key else "ssh-agent/default keys"
    identity_file = input(
        f"Путь к приватному ключу [{key_prompt}] "
        "(пусто — оставить текущее; '-' — ssh-agent/default keys): "
    ).strip()
    if identity_file == "-":
        identity_file = ""
    elif not identity_file:
        identity_file = old_key
    settings = validate_settings({
        "host": host,
        "port": port_text,
        "username": username,
        "identity_file": identity_file,
    })
    candidate = dict(cfg)
    candidate["ssh"] = settings
    client = SshClient(candidate)
    client.check_root()
    cfg["ssh"] = settings
    save_config(cfg)
    print("SSH проверен: соединение по ключу работает, удалённый UID = 0.")
    print("Параметры сохранены локально; содержимое приватного ключа никуда не копируется.")


def _client(cfg):
    client = SshClient(cfg)
    client.check_root()
    return client


def _backup_boot_script(client):
    text = client.run(BOOT_BACKUP_SCRIPT, timeout=15, strip_output=False)
    if not text.strip():
        raise UserError("SSH вернул пустой boot script; резервная копия не создана.")
    folder = STATE / "ssh-backups"
    folder.mkdir(parents=True, exist_ok=True)
    folder.chmod(0o700)
    name = "myscript-max-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".sh"
    destination = folder / name
    with destination.open("w", encoding="utf-8", newline="") as stream:
        stream.write(text)
    destination.chmod(0o600)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    print("Локальная резервная копия:", destination)
    print("SHA256:", digest)
    print("Файл может содержать чувствительные настройки; не добавляйте его в Git или публичные отчёты.")


def manage_menu(cfg):
    while True:
        configured = isinstance(cfg.get("ssh"), dict)
        state = "настроено" if configured else "не настроено"
        choice = show_menu(
            f"Управление MaxWave по SSH — {state}",
            [
                ("1", "Настроить или проверить SSH-подключение"),
                ("2", "Проверить SSH и UID root"),
                ("3", "Показать состояние MaxWave"),
                ("4", "Проверить скрипты, token и boot hook"),
                ("5", "Сделать локальную копию myscript-max.sh"),
                ("6", "Запустить MaxWave"),
                ("7", "Остановить MaxWave"),
                ("8", "Перезапустить MaxWave"),
                ("9", "Показать последние строки журналов daemon.log"),
                ("10", "Удалить локальные параметры SSH"),
                ("0", "Назад"),
            ],
        )
        if choice == "0":
            return
        try:
            if choice == "1":
                _configure(cfg)
            elif choice == "2":
                _client(cfg)
                print("SSH доступен; удалённый UID = 0.")
            elif choice == "3":
                print(_client(cfg).run(STATUS_SCRIPT, timeout=15))
            elif choice == "4":
                print(_client(cfg).run(VALIDATE_SCRIPT, timeout=20))
            elif choice == "5":
                _backup_boot_script(_client(cfg))
            elif choice == "6":
                client = _client(cfg)
                print(client.run(START_SCRIPT, timeout=25))
                print(client.run(STATUS_SCRIPT, timeout=15))
            elif choice == "7":
                if input("Остановить установленный сервис MaxWave? [y/N]: ").strip().lower() != "y":
                    print("Остановка отменена.")
                    continue
                client = _client(cfg)
                print(client.run(STOP_SCRIPT, timeout=25))
                print(client.run(STATUS_SCRIPT, timeout=15))
            elif choice == "8":
                if input("Перезапустить установленный сервис MaxWave? [y/N]: ").strip().lower() != "y":
                    print("Перезапуск отменён.")
                    continue
                print(_client(cfg).run(RESTART_SCRIPT, timeout=45))
                print("Команда перезапуска завершена.")
            elif choice == "9":
                print(_client(cfg).run(LOG_SCRIPT, timeout=15))
            elif choice == "10":
                if input("Удалить только локальные параметры SSH? [y/N]: ").strip().lower() == "y":
                    cfg.pop("ssh", None)
                    save_config(cfg)
                    print("Локальные параметры SSH удалены. Сервер, ключ и known_hosts не затронуты.")
        except UserError as exc:
            print("Ошибка SSH:", exc)
