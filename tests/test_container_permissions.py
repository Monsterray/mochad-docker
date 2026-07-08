from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ContainerPermissionsTests(unittest.TestCase):
    def test_entrypoint_has_valid_shell_syntax(self) -> None:
        subprocess.run(
            ["sh", "-n", str(ROOT / "mochad-entrypoint.sh")],
            check=True,
        )

    def test_entrypoint_prepares_config_and_validates_usb_before_drop(self) -> None:
        entrypoint = (ROOT / "mochad-entrypoint.sh").read_text()

        self.assertIn('PUID="${PUID:-911}"', entrypoint)
        self.assertIn('PGID="${PGID:-911}"', entrypoint)
        self.assertIn('USB_GID="${USB_GID:-911}"', entrypoint)
        self.assertIn('UMASK="${UMASK:-022}"', entrypoint)
        self.assertIn('chown -R "$PUID:$PGID" /config', entrypoint)
        self.assertIn("find /dev/bus/usb -type c", entrypoint)
        self.assertIn("0bc7:0001|0bc7:0002", entrypoint)
        self.assertIn("x10_nodes", entrypoint)
        self.assertIn('su-exec "$runtime_user"', entrypoint)
        self.assertIn('exec su-exec "$runtime_user" "$@"', entrypoint)
        self.assertNotIn("chown -R \"$PUID:$PGID\" /usr/local", entrypoint)

    def test_compose_uses_usb_cgroup_rule_not_privileged_mode(self) -> None:
        compose = (ROOT / "docker-compose.yml").read_text()

        self.assertIn("/dev/bus/usb:/dev/bus/usb", compose)
        self.assertIn('"c 189:* rwm"', compose)
        self.assertIn("USB_GID:", compose)
        self.assertNotIn("privileged: true", compose)
        self.assertNotIn("SYS_ADMIN", compose)
        self.assertNotIn("SYS_RAWIO", compose)
