from io import BytesIO
from pathlib import Path
import json
import subprocess
import tarfile
import tempfile
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
        self.assertIn('USB_GID="${USB_GID:-auto}"', entrypoint)
        self.assertIn('USB_DEBUG="${USB_DEBUG:-false}"', entrypoint)
        self.assertIn('UMASK="${UMASK:-022}"', entrypoint)
        self.assertIn('chown -R "$PUID:$PGID" /config', entrypoint)
        self.assertIn("find /dev/bus/usb -type c", entrypoint)
        self.assertIn("0bc7:0001|0bc7:0002", entrypoint)
        self.assertIn("x10_nodes", entrypoint)
        self.assertIn("auto-detected USB_GID", entrypoint)
        self.assertIn('su-exec "$runtime_user"', entrypoint)
        self.assertIn('exec su-exec "$runtime_user" "$@"', entrypoint)
        self.assertNotIn("chown -R \"$PUID:$PGID\" /usr/local", entrypoint)

    def test_compose_uses_usb_cgroup_rule_not_privileged_mode(self) -> None:
        compose = (ROOT / "docker-compose.yml").read_text()

        self.assertIn("/dev/bus/usb:/dev/bus/usb", compose)
        self.assertIn('"c 189:* rwm"', compose)
        self.assertIn("USB_GID:", compose)
        self.assertIn("${USB_GID:-auto}", compose)
        self.assertNotIn("privileged: true", compose)
        self.assertNotIn("SYS_ADMIN", compose)
        self.assertNotIn("SYS_RAWIO", compose)

    def test_dockerfile_installs_separate_license_trees(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text()

        self.assertIn("/usr/share/licenses/mochad-docker", dockerfile)
        self.assertIn("/usr/share/licenses/mochad-redux", dockerfile)
        self.assertIn("COPY LICENSE.md /usr/share/licenses/mochad-docker/LICENSE.md", dockerfile)
        self.assertIn("/tmp/runtime-licenses/mochad-redux/", dockerfile)
        self.assertIn("COPYING NOTICE docs/source-lineage.md", dockerfile)
        self.assertIn('org.opencontainers.image.licenses="MIT AND GPL-3.0-or-later"', dockerfile)

    def test_dockerfile_uses_a_runtime_libusb_package_and_configurable_base(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text()

        self.assertIn("ARG ALPINE_BASE_IMAGE=alpine:3.22", dockerfile)
        self.assertIn("FROM ${ALPINE_BASE_IMAGE} AS builder", dockerfile)
        self.assertIn("FROM ${ALPINE_BASE_IMAGE}", dockerfile)
        runtime_stage = dockerfile.split("# Runtime Stage", maxsplit=1)[1]
        self.assertIn("    libusb", runtime_stage)
        self.assertNotIn("libusb-dev", runtime_stage)

    def test_release_workflow_builds_the_resolved_redux_revision(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release-image.yml").read_text()

        self.assertIn("MOCHAD_REF=${{ steps.release-meta.outputs.redux_sha }}", workflow)
        self.assertIn("MOCHAD_REDUX_REVISION=${{ steps.release-meta.outputs.redux_sha }}", workflow)
        self.assertIn("ALPINE_BASE_IMAGE=docker.io/library/alpine@${{ steps.release-meta.outputs.alpine_digest }}", workflow)
        self.assertIn("REQUIRE_AUDITED_SOURCE=true", workflow)

    def test_workflows_use_current_docker_action_majors(self) -> None:
        workflows = (ROOT / ".github" / "workflows").glob("*.yml")
        content = "\n".join(path.read_text() for path in workflows)

        self.assertNotIn("docker/setup-qemu-action@v3", content)
        self.assertNotIn("docker/setup-buildx-action@v3", content)
        self.assertNotIn("docker/build-push-action@v6", content)
        self.assertNotIn("docker/login-action@v3", content)
        self.assertIn("docker/setup-qemu-action@v4", content)
        self.assertIn("docker/setup-buildx-action@v4", content)
        self.assertIn("docker/build-push-action@v7", content)
        self.assertNotIn("--format '{{ .Digest }}'", content)
        self.assertIn("--format '{{ .Manifest.Digest }}'", content)
        self.assertIn("--output type=oci,dest=/tmp/mochad-ci-index.tar", content)
        self.assertNotIn("localhost:5000/x10-mochad:ci-index", content)

    def test_oci_archive_validator_reads_platforms_from_image_configs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / "image.tar"
            blobs = {
                "blobs/sha256/nested-index": {
                    "schemaVersion": 2,
                    "manifests": [
                        {"digest": "sha256:amd64-manifest"},
                        {"digest": "sha256:arm64-manifest"},
                    ],
                },
                "blobs/sha256/amd64-manifest": {"config": {"digest": "sha256:amd64-config"}},
                "blobs/sha256/arm64-manifest": {"config": {"digest": "sha256:arm64-config"}},
                "blobs/sha256/amd64-config": {"os": "linux", "architecture": "amd64"},
                "blobs/sha256/arm64-config": {"os": "linux", "architecture": "arm64"},
            }
            index = {
                "schemaVersion": 2,
                "manifests": [
                    {"digest": "sha256:nested-index"},
                ],
            }

            with tarfile.open(archive_path, "w") as archive:
                for name, data in {"index.json": index, **blobs}.items():
                    encoded = json.dumps(data).encode()
                    member = tarfile.TarInfo(name)
                    member.size = len(encoded)
                    archive.addfile(member, fileobj=BytesIO(encoded))

            result = subprocess.run(
                [str(ROOT / "scripts" / "validate-oci-index.sh"), "--archive", str(archive_path)],
                check=True,
                capture_output=True,
                text=True,
            )

        self.assertIn("PASS: OCI archive contains linux/amd64 and linux/arm64", result.stdout)
