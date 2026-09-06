import io
import json
import os
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.backup.backup_restore import (
    BackupError,
    create_backup,
    inspect_backup,
    restore,
)

SHA = "a" * 40


def _source(root: Path) -> None:
    (root / "release").mkdir()
    (root / "VERSION").write_text("0.4.0\n", encoding="utf-8")
    (root / "docker-compose.yml").write_text(
        "services:\n  mochad:\n    image: x10-mochad:local\n",
        encoding="utf-8",
    )
    (root / "release/versions.env").write_text(
        f"IMAGE_VERSION=0.4.0\nMOCHAD_SOURCE_SHA={SHA}\n",
        encoding="utf-8",
    )


def _rewrite(path: Path, mutate) -> None:
    with tarfile.open(path, "r:gz") as archive:
        members = {
            member.name: archive.extractfile(member).read()
            for member in archive.getmembers()
        }
    mutate(members)
    with tarfile.open(path, "w:gz") as archive:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))


class BackupRestoreTests(unittest.TestCase):
    def test_backup_contains_only_owned_inputs_and_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            _source(source)
            environment = source / ".env"
            environment.write_text(
                "PUID=12345\nMQTT_PASSWORD=hidden\nUNKNOWN=value\n"
                "MOCHAD_PORT=1099\n",
                encoding="utf-8",
            )
            archive = root / "backup.tar.gz"

            manifest = create_backup(
                source,
                archive,
                environment_file=environment,
                repository_sha=SHA,
            )

            with tarfile.open(archive, "r:gz") as bundle:
                names = set(bundle.getnames())
                saved_environment = bundle.extractfile(
                    "files/deployment.env"
                ).read()
            self.assertEqual(
                {
                    "manifest.json",
                    "files/docker-compose.yml",
                    "files/release/versions.env",
                    "files/deployment.env",
                },
                names,
            )
            self.assertEqual(b"MOCHAD_PORT=1099\nPUID=12345\n", saved_environment)
            self.assertEqual(
                "UNSANITIZED OPERATIONAL BACKUP",
                manifest["classification"],
            )
            self.assertTrue(
                all(
                    item["value"] is None
                    for item in manifest["external_secret_placeholders"]
                )
            )

    def test_backup_rejects_secret_material(self):
        cases = (
            (
                "docker-compose.yml",
                b"image: mqtt://user:password@example.invalid\n",
            ),
            (
                "release/versions.env",
                b"KEY=-----BEGIN PRIVATE KEY-----\n",
            ),
        )
        for name, data in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    source = root / "source"
                    source.mkdir()
                    _source(source)
                    (source / name).write_bytes(data)
                    with self.assertRaisesRegex(BackupError, "secret material"):
                        create_backup(
                            source,
                            root / "backup.tar.gz",
                            repository_sha=SHA,
                        )

    def test_inspection_fails_closed(self):
        for failure in ("checksum", "schema", "extra"):
            with self.subTest(failure=failure):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    source = root / "source"
                    source.mkdir()
                    _source(source)
                    archive = root / "backup.tar.gz"
                    create_backup(source, archive, repository_sha=SHA)

                    def mutate(members):
                        if failure == "checksum":
                            members["files/docker-compose.yml"] += b"# changed\n"
                        elif failure == "schema":
                            manifest = json.loads(members["manifest.json"])
                            manifest["schema_version"] = 99
                            members["manifest.json"] = json.dumps(manifest).encode()
                        else:
                            members["files/unexpected"] = b"unexpected"

                    _rewrite(archive, mutate)
                    with self.assertRaises(BackupError):
                        inspect_backup(archive)

    def test_restore_dry_run_overwrite_apply_and_idempotence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            _source(source)
            archive = root / "backup.tar.gz"
            create_backup(source, archive, repository_sha=SHA)
            target = root / "isolated"
            existing = target / "docker-compose.yml"
            existing.parent.mkdir()
            existing.write_text("old\n", encoding="utf-8")

            plan = restore(archive, target)
            self.assertEqual("replace", plan["plan"][0]["action"])
            with self.assertRaisesRegex(BackupError, "pass --overwrite"):
                restore(archive, target, apply=True)
            restore(archive, target, apply=True, overwrite=True)
            repeated = restore(archive, target, apply=True)
            self.assertEqual(
                {"unchanged"},
                {item["action"] for item in repeated["plan"]},
            )

    def test_activation_failure_rolls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            _source(source)
            archive = root / "backup.tar.gz"
            create_backup(source, archive, repository_sha=SHA)
            target = root / "isolated"
            (target / "release").mkdir(parents=True)
            old_compose = b"old compose\n"
            old_versions = b"old versions\n"
            (target / "docker-compose.yml").write_bytes(old_compose)
            (target / "release/versions.env").write_bytes(old_versions)
            real_replace = os.replace

            def fail(source_path, destination_path):
                if str(source_path).endswith(
                    "payload/files/release/versions.env"
                ):
                    raise OSError("synthetic activation failure")
                return real_replace(source_path, destination_path)

            with mock.patch("os.replace", side_effect=fail):
                with self.assertRaisesRegex(
                    BackupError,
                    "synthetic activation failure",
                ):
                    restore(archive, target, apply=True, overwrite=True)
            self.assertEqual(
                old_compose,
                (target / "docker-compose.yml").read_bytes(),
            )
            self.assertEqual(
                old_versions,
                (target / "release/versions.env").read_bytes(),
            )

    def test_restore_refuses_root_and_stale_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            _source(source)
            archive = root / "backup.tar.gz"
            manifest = create_backup(source, archive, repository_sha=SHA)
            with self.assertRaisesRegex(BackupError, "not isolated"):
                restore(archive, Path("/"))
            target = root / "isolated"
            (target / f".mochad-docker-restore-{manifest['backup_id']}").mkdir(
                parents=True
            )
            with self.assertRaisesRegex(BackupError, "staging path exists"):
                restore(archive, target, apply=True)


if __name__ == "__main__":
    unittest.main()
