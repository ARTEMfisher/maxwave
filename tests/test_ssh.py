import pathlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from maxwave import ssh
from maxwave.common import UserError


class SshSettingsTests(unittest.TestCase):
    def test_valid_settings_and_defaults(self):
        value = ssh.validate_settings({
            "host": "192.168.50.146",
            "port": "2222",
            "username": "root",
        })
        self.assertEqual(value["host"], "192.168.50.146")
        self.assertEqual(value["port"], 2222)
        self.assertEqual(value["username"], "root")
        self.assertEqual(value["identity_file"], "")

    def test_rejects_host_injection_and_urls(self):
        for host in ["", "-oProxyCommand=bad", "ssh://192.168.1.5", "host;id", "host name"]:
            with self.subTest(host=host), self.assertRaises(UserError):
                ssh.validate_settings({"host": host})

    def test_rejects_invalid_port_and_username(self):
        for port in [0, 65536, "abc", "22;id"]:
            with self.subTest(port=port), self.assertRaises(UserError):
                ssh.validate_settings({"host": "station.local", "port": port})
        for username in ["", "-oProxyCommand=bad", "root;id", "root name"]:
            with self.subTest(username=username), self.assertRaises(UserError):
                ssh.validate_settings({"host": "station.local", "username": username})

    def test_requires_private_key_path_when_configured(self):
        with tempfile.TemporaryDirectory() as folder:
            key = pathlib.Path(folder) / "id_ed25519"
            key.write_text("not read by MaxWave", encoding="utf-8")
            value = ssh.validate_settings({
                "host": "station.local",
                "identity_file": str(key),
            })
            self.assertEqual(value["identity_file"], str(key.resolve()))
            with self.assertRaises(UserError):
                ssh.validate_settings({
                    "host": "station.local",
                    "identity_file": str(key) + ".missing",
                })
            with self.assertRaises(UserError):
                ssh.validate_settings({
                    "host": "station.local",
                    "identity_file": str(key) + ".pub",
                })
            ppk = pathlib.Path(folder) / "id_ed25519.ppk"
            ppk.write_text("private", encoding="utf-8")
            with self.assertRaises(UserError):
                ssh.validate_settings({
                    "host": "station.local",
                    "identity_file": str(ppk),
                })


class SshClientTests(unittest.TestCase):
    def _client(self, identity_file=""):
        settings = {
            "host": "192.168.50.146",
            "port": 2222,
            "username": "root",
            "identity_file": identity_file,
        }
        with patch.object(ssh.shutil, "which", return_value="ssh"):
            return ssh.SshClient({"ssh": settings})

    def test_command_enforces_key_auth_and_host_verification(self):
        with tempfile.TemporaryDirectory() as folder:
            key = pathlib.Path(folder) / "id_ed25519"
            key.write_text("placeholder", encoding="utf-8")
            command = self._client(str(key))._command()
        self.assertIn("root@192.168.50.146", command)
        self.assertIn("-p", command)
        self.assertIn("2222", command)
        self.assertIn("StrictHostKeyChecking=yes", command)
        self.assertIn("PasswordAuthentication=no", command)
        self.assertIn("KbdInteractiveAuthentication=no", command)
        self.assertIn("PreferredAuthentications=publickey", command)
        self.assertIn("BatchMode=yes", command)
        self.assertIn("ForwardAgent=no", command)
        self.assertIn("ClearAllForwardings=yes", command)
        self.assertEqual(command[-1], "/system/bin/sh -s")

    def test_run_sends_script_over_stdin(self):
        client = self._client()
        completed = subprocess.CompletedProcess([], 0, "ok\n", "")
        with patch.object(ssh.subprocess, "run", return_value=completed) as run:
            self.assertEqual(client.run("id -u\n"), "ok")
        kwargs = run.call_args.kwargs
        self.assertEqual(kwargs["input"], "id -u\n")
        self.assertTrue(kwargs["capture_output"])
        self.assertEqual(kwargs["timeout"], 25)

    def test_run_can_preserve_file_content_and_newlines(self):
        client = self._client()
        original = "#!/system/bin/sh\n# Station configuration\n\n"
        completed = subprocess.CompletedProcess([], 0, original, "")
        with patch.object(ssh.subprocess, "run", return_value=completed):
            self.assertEqual(client.run("cat /path\n", strip_output=False), original)

    def test_rejects_nul_in_remote_script(self):
        client = self._client()
        with self.assertRaises(UserError):
            client.run("echo ok\x00bad")

    def test_host_key_failure_is_reported_without_disabling_verification(self):
        client = self._client()
        completed = subprocess.CompletedProcess([], 255, "", "Host key verification failed.")
        with patch.object(ssh.subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(UserError, "host key"):
                client.run("id -u\n")

    def test_password_authentication_failure_is_reported(self):
        client = self._client()
        completed = subprocess.CompletedProcess([], 255, "", "Permission denied (publickey).")
        with patch.object(ssh.subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(UserError, "аутентификация"):
                client.run("id -u\n")

    def test_root_check_requires_uid_zero(self):
        client = self._client()
        with patch.object(client, "run", return_value="0\n"):
            self.assertEqual(client.check_root(), "0")
        with patch.object(client, "run", return_value="2000\n"):
            with self.assertRaisesRegex(UserError, "не root"):
                client.check_root()

    def test_missing_openssh_client_is_reported(self):
        with patch.object(ssh.shutil, "which", return_value=None):
            with self.assertRaisesRegex(UserError, "OpenSSH client"):
                ssh.SshClient({"ssh": {"host": "station.local"}})


if __name__ == "__main__":
    unittest.main()



class SshRemoteScriptTests(unittest.TestCase):
    def test_management_scripts_require_project_owner_marker(self):
        scripts = [
            ssh.STATUS_SCRIPT,
            ssh.VALIDATE_SCRIPT,
            ssh.BOOT_BACKUP_SCRIPT,
            ssh.START_SCRIPT,
            ssh.STOP_SCRIPT,
            ssh.RESTART_SCRIPT,
            ssh.LOG_SCRIPT,
        ]
        for script in scripts:
            with self.subTest(script=script[:32]):
                self.assertIn(ssh.OWNER_MARKER, script)

    def test_validation_never_prints_ipc_token_value(self):
        self.assertIn('token=$(cat "$D/token"', ssh.VALIDATE_SCRIPT)
        self.assertIn("IPC token: length OK", ssh.VALIDATE_SCRIPT)
        self.assertNotIn('echo "$token"', ssh.VALIDATE_SCRIPT)
        self.assertNotIn('printf "$token"', ssh.VALIDATE_SCRIPT)

    def test_management_scripts_use_only_existing_control_scripts(self):
        self.assertIn('/system/bin/sh "$D/start.sh"', ssh.START_SCRIPT)
        self.assertIn('/system/bin/sh "$D/stop.sh"', ssh.STOP_SCRIPT)
        self.assertIn('/system/bin/sh "$D/stop.sh"', ssh.RESTART_SCRIPT)
        self.assertIn('/system/bin/sh "$D/start.sh"', ssh.RESTART_SCRIPT)
        self.assertNotIn("setenforce", ssh.START_SCRIPT + ssh.STOP_SCRIPT + ssh.RESTART_SCRIPT)
        self.assertNotIn("dropbear", ssh.START_SCRIPT + ssh.STOP_SCRIPT + ssh.RESTART_SCRIPT)
        self.assertNotIn("rootd", ssh.START_SCRIPT + ssh.STOP_SCRIPT + ssh.RESTART_SCRIPT)
        self.assertIn("did not start within 20 seconds", ssh.START_SCRIPT)
        self.assertIn("did not stop within 15 seconds", ssh.STOP_SCRIPT)
        self.assertIn("did not restart within 20 seconds", ssh.RESTART_SCRIPT)


