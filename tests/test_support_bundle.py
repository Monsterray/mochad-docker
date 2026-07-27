from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "support" / "collect-support-bundle.py"
SPEC = importlib.util.spec_from_file_location("support_bundle", SCRIPT)
assert SPEC and SPEC.loader
support_bundle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(support_bundle)


class SupportBundleTests(unittest.TestCase):
    def test_manifest_archive_and_permissions_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "support.tar.gz"
            builder = support_bundle.BundleBuilder(
                output,
                "a" * 40,
                created_at="2026-07-26T00:00:00Z",
                bundle_id="test-bundle",
            )
            builder.components.append(
                {
                    "repository": "mochad-docker",
                    "version": "0.4.0",
                    "sha": "a" * 40,
                    "ref": None,
                    "dirty": False,
                }
            )
            builder.add_json(
                "oci-image-metadata",
                "image/oci.json",
                {"architecture": "amd64", "labels": {}},
                "image",
                "public",
                "allowlisted image inspection",
            )
            builder.omit("runtime-identity", "runtime", "not selected")
            builder.write()

            self.assertEqual(0o600, output.stat().st_mode & 0o777)
            with tarfile.open(output, "r:gz") as archive:
                names = archive.getnames()
                self.assertEqual(
                    ["image", "image/oci.json", "manifest.json", "scan-result.json"],
                    names,
                )
                self.assertTrue(all(member.uid == 0 for member in archive.getmembers()))
                manifest = json.load(archive.extractfile("manifest.json"))
                scan_result = json.load(archive.extractfile("scan-result.json"))
                self.assertEqual(0o600, archive.getmember("image/oci.json").mode)

            self.assertEqual(1, manifest["schema_version"])
            self.assertEqual("test-bundle", manifest["bundle_id"])
            self.assertEqual("PASS", manifest["secret_scan"]["status"])
            self.assertTrue(manifest["secret_scan"]["archive_scanned"])
            self.assertEqual(scan_result, manifest["secret_scan"])
            self.assertEqual(
                {"generator", "components", "redaction", "entries", "secret_scan"}
                - set(manifest),
                set(),
            )
            collected = next(item for item in manifest["entries"] if item["status"] == "collected")
            self.assertEqual(64, len(collected["sha256"]))

    def test_secret_or_forbidden_filename_fails_closed(self) -> None:
        cases = (
            ("safe.txt", "password=correct-horse-battery-staple\n"),
            (".env", "SAFE=true\n"),
            ("safe.txt", "token_abcdEFGHijklMNOPqrstUVWXyz0123456789\n"),
        )
        for name, content in cases:
            with self.subTest(name=name, content=content):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    output = Path(temporary_directory) / "support.tar.gz"
                    builder = support_bundle.BundleBuilder(
                        output,
                        "a" * 40,
                        created_at="2026-07-26T00:00:00Z",
                    )
                    builder.add_text("unsafe", name, content, "test", "sensitive", "fixture")
                    with self.assertRaises(support_bundle.SecretScanError):
                        builder.write()
                    self.assertFalse(output.exists())

    def test_failed_collection_preserves_existing_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "support.tar.gz"
            output.write_bytes(b"previous valid evidence")
            builder = support_bundle.BundleBuilder(
                output,
                "a" * 40,
                created_at="2026-07-26T00:00:00Z",
            )
            builder.add_text(
                "unsafe",
                "unsafe.txt",
                "password=hidden\n",
                "test",
                "secret",
                "fixture",
            )
            with self.assertRaises(support_bundle.SecretScanError):
                builder.write()
            self.assertEqual(b"previous valid evidence", output.read_bytes())

    def test_archive_scanner_reads_member_names_and_contents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / "tampered.tar.gz"
            with tarfile.open(archive_path, "w:gz") as archive:
                data = b"authorization: Bearer hidden-value\n"
                member = tarfile.TarInfo("logs/output.txt")
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
            findings = support_bundle.scan_archive(archive_path)
        self.assertEqual("logs/output.txt", findings[0]["path"])
        self.assertIn("credential_assignment", findings[0]["classes"])

    def test_manifest_and_completed_archive_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "support.tar.gz"
            builder = support_bundle.BundleBuilder(
                output,
                "a" * 40,
                created_at="2026-07-26T00:00:00Z",
            )
            builder.components.append({"password": "hidden"})
            with self.assertRaises(support_bundle.SecretScanError):
                builder.write()
            self.assertFalse(output.exists())

            builder = support_bundle.BundleBuilder(
                output,
                "a" * 40,
                created_at="2026-07-26T00:00:00Z",
            )
            with mock.patch.object(
                support_bundle,
                "scan_archive",
                return_value=[{"path": "manifest.json", "classes": ["tampered"]}],
            ):
                with self.assertRaises(support_bundle.SecretScanError):
                    builder.write()
            self.assertFalse(output.exists())

    def test_compose_sanitizer_keeps_structure_not_values_or_secrets(self) -> None:
        aliases = support_bundle.Aliases()
        source = {
            "name": "private-project",
            "services": {
                "mochad-prod": {
                    "image": "private.registry.example/mochad:secret-tag",
                    "build": {"context": "/home/alice/private"},
                    "environment": {
                        "PUID": "12345",
                        "MOCHAD_ARGS": "--password hidden",
                        "UNRELATED_SECRET": "hidden",
                    },
                    "ports": [{"target": 1099, "published": "31099", "host_ip": "10.0.0.2"}],
                    "volumes": [
                        {
                            "type": "bind",
                            "source": "/home/alice/config",
                            "target": "/config",
                        }
                    ],
                    "secrets": [{"source": "mqtt_password"}],
                    "healthcheck": {"test": ["CMD", "secret"]},
                }
            },
            "secrets": {"mqtt_password": {"file": "/home/alice/password"}},
            "networks": {"prod": {}},
            "volumes": {"config": {}},
        }
        sanitized = support_bundle.sanitize_compose(source, aliases)
        encoded = json.dumps(sanitized)

        self.assertNotIn("alice", encoded)
        self.assertNotIn("hidden", encoded)
        self.assertNotIn("MOCHAD_ARGS", encoded)
        self.assertNotIn("UNRELATED_SECRET", encoded)
        self.assertNotIn("mqtt_password", encoded)
        self.assertNotIn("31099", encoded)
        self.assertNotIn("10.0.0.2", encoded)
        self.assertIn("PUID", encoded)
        self.assertIn('"target": 1099', encoded)
        self.assertIn('"target": "/config"', encoded)
        self.assertEqual("SERVICE_1", sanitized["services"][0]["name"])
        self.assertEqual("IMAGE_1", sanitized["services"][0]["image"])

    def test_oci_and_build_info_use_exact_allowlists(self) -> None:
        responses = {
            "{{json .Config.Labels}}": {
                "org.opencontainers.image.version": "0.4.0",
                "org.opencontainers.image.source": "https://user:pass@example.test/repo",
                "untrusted.secret": "hidden",
            },
            "{{json .RepoDigests}}": ["private.example/repo@sha256:" + "a" * 64],
            "{{json .Id}}": "sha256:" + "b" * 64,
            "{{json .Os}}": "linux",
            "{{json .Architecture}}": "amd64",
            "{{json .Config.Entrypoint}}": ["/usr/local/bin/mochad-entrypoint.sh"],
            "{{json .Config.Cmd}}": ["/usr/local/bin/mochad", "--foreground"],
        }

        class FakeDocker:
            def format(self, _image: str, template: str):
                return responses[template]

            def run(self, *_arguments: str) -> str:
                return json.dumps(
                    {
                        "name": "mochad-docker",
                        "version": "0.4.0",
                        "mochad_source_sha": "c" * 40,
                        "mochad_repository": "https://user:pass@example.test/redux",
                        "password": "hidden",
                    }
                )

        oci = support_bundle.collect_oci(FakeDocker(), "image")
        build_info = support_bundle.collect_build_info(FakeDocker(), "image")
        encoded = json.dumps([oci, build_info])
        self.assertNotIn("pass", encoded)
        self.assertNotIn("untrusted.secret", encoded)
        self.assertNotIn("password", encoded)
        self.assertEqual(["sha256:" + "a" * 64], oci["digests"])
        self.assertEqual("https://example.test/repo", oci["labels"]["org.opencontainers.image.source"])
        self.assertEqual("https://example.test/redux", build_info["mochad_repository"])

    def test_logs_are_bounded_and_pseudonymized(self) -> None:
        lines = [f"ordinary line {number}" for number in range(1_010)]
        lines.extend(
            [
                "connecting to 192.168.8.99 from /home/alice/config",
                "Security RF identifier 123456",
                "password=hidden",
            ]
        )
        redacted, applied = support_bundle.bound_log(
            "\n".join(lines),
            1_000,
            support_bundle.Aliases(),
        )
        self.assertLessEqual(len(redacted.encode()), support_bundle.MAX_LOG_BYTES + 100)
        self.assertNotIn("192.168.8.99", redacted)
        self.assertNotIn("/home/alice/config", redacted)
        self.assertNotIn("123456", redacted)
        self.assertNotIn("hidden", redacted)
        self.assertIn("HOST_1", redacted)
        self.assertIn("[REDACTED:security_rf]", redacted)
        self.assertIn("[REDACTED:credential]", redacted)
        self.assertIn("security_rf", applied)

    def test_docker_log_collection_includes_both_streams(self) -> None:
        result = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="stdout line\n",
            stderr="stderr line\n",
        )
        with mock.patch.object(support_bundle.subprocess, "run", return_value=result) as run:
            logs = support_bundle.Docker().logs("private-container", 20)
        self.assertEqual("stdout line\nstderr line\n", logs)
        self.assertEqual(
            ["docker", "logs", "--tail", "20", "private-container"],
            run.call_args.args[0],
        )

    def test_runtime_identity_is_pseudonymized(self) -> None:
        outputs = iter(["12345\n", "23456\n", "23456 34567\n"])

        class FakeDocker:
            def run(self, *_arguments: str) -> str:
                return next(outputs)

        identity = support_bundle.collect_runtime_identity(
            FakeDocker(),
            "production-mochad",
            support_bundle.Aliases(),
        )
        self.assertEqual("CONTAINER_1", identity["container"])
        self.assertEqual("USER_1", identity["uid"])
        self.assertEqual("GROUP_1", identity["gid"])
        self.assertEqual(["GROUP_1", "GROUP_2"], identity["supplementary_groups"])

    def test_dry_run_does_not_call_docker(self) -> None:
        result = subprocess.run(
            [
                os.environ.get("PYTHON", "python3"),
                str(SCRIPT),
                "--image",
                "example",
                "--output",
                "ignored.tar.gz",
                "--dry-run",
            ],
            check=True,
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        plan = json.loads(result.stdout)
        self.assertEqual("IMAGE_1", plan["image"])
        self.assertFalse((ROOT / "ignored.tar.gz").exists())

    @unittest.skipUnless(
        os.environ.get("MOCHAD_DOCKER_SMOKE_IMAGE"),
        "set MOCHAD_DOCKER_SMOKE_IMAGE for the optional Docker smoke test",
    )
    def test_optional_docker_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "support.tar.gz"
            subprocess.run(
                [
                    os.environ.get("PYTHON", "python3"),
                    str(SCRIPT),
                    "--image",
                    os.environ["MOCHAD_DOCKER_SMOKE_IMAGE"],
                    "--output",
                    str(output),
                ],
                check=True,
                cwd=ROOT,
            )
            self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()
