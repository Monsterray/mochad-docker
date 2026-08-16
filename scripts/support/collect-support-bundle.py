#!/usr/bin/env python3
"""Create a bounded, sanitized mochad-docker support bundle."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit
import uuid


SCHEMA_VERSION = 1
GENERATOR_VERSION = "1.0.0"
MAX_LOG_LINES = 1_000
MAX_LOG_BYTES = 128 * 1024
MAX_TEXT_BYTES = 256 * 1024

ALLOWED_OCI_LABELS = {
    "org.opencontainers.image.title",
    "org.opencontainers.image.description",
    "org.opencontainers.image.created",
    "org.opencontainers.image.version",
    "org.opencontainers.image.revision",
    "org.opencontainers.image.source",
    "org.opencontainers.image.licenses",
    "org.opencontainers.image.base.name",
    "org.opencontainers.image.base.digest",
    "io.github.monsterray.mochad-redux.repository",
    "io.github.monsterray.mochad-redux.revision",
    "io.github.monsterray.mochad-redux.version",
}
ALLOWED_BUILD_INFO = {
    "name",
    "version",
    "mochad_repository",
    "mochad_source_sha",
    "mochad_redux_version",
    "alpine_image",
    "alpine_digest",
}
ALLOWED_ENVIRONMENT_KEYS = {
    "MOCHAD_BIND",
    "MOCHAD_FOREGROUND",
    "MOCHAD_OPENREMOTE_ENABLED",
    "MOCHAD_OPENREMOTE_PORT",
    "MOCHAD_PORT",
    "MOCHAD_RAW_DATA",
    "MOCHAD_SHOW_HELP",
    "MOCHAD_SHOW_VERSION",
    "MOCHAD_XML_ENABLED",
    "MOCHAD_XML_PORT",
    "PGID",
    "PUID",
    "TZ",
    "UMASK",
    "USB_DEBUG",
    "USB_GID",
}

# `_` is a word character, so a plain `\b` cannot see a keyword embedded in an
# underscore-joined identifier such as DB_PASSWORD or MQTT_TLS_KEY_PASSWORD --
# the boundary check right before/after the keyword never fires. These two
# fragments treat a chain of underscore-joined alnum segments on either side
# of the keyword as part of the same identifier, so the keyword is still
# recognised wherever it appears as a whole segment of a longer name (this
# generalises what used to be one-off literal entries like "mqtt_password").
_KEY_PREFIX = r"(?:^|[^A-Za-z0-9])(?:[A-Za-z0-9]+_)*"
_KEY_SUFFIX = r"(?:_[A-Za-z0-9]+)*"
_KEYWORD = r"(?:auth|authorization|password|passwd|secret|token|api[_-]?key)"

SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    # The "not already redacted" guard sits immediately after the
    # single-character [=:]. Placed after the following \s*, the engine
    # backtracks one space, evaluates it against " [REDACTED:...", finds it
    # passes, and flags the line anyway -- which fails the build on every
    # bundle that contains a sanitised Authorization header.
    "credential_assignment": re.compile(
        rf"(?i){_KEY_PREFIX}{_KEYWORD}{_KEY_SUFFIX}\s*[=:]"
        r"(?!\s*[\"']?\[REDACTED:)\s*"
    ),
    "url_userinfo": re.compile(
        r"\b[a-z][a-z0-9+.-]*://(?!\[REDACTED:)[^/\s@]+@"),
}
FORBIDDEN_FILENAME = re.compile(
    r"(?i)(?:^|/)(?:\.env(?:[./]|$)|id_(?:rsa|dsa|ecdsa|ed25519)(?:\.pub)?$|"
    r"[^/]*(?:credential|password|private[-_]?key|secret|token)[^/]*$)"
)
HIGH_ENTROPY_CANDIDATE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9_+/=-]{32,}(?![A-Za-z0-9])")
URL_USERINFO = re.compile(r"\b([a-z][a-z0-9+.-]*://)(?!\[REDACTED:)[^/\s@]+@", re.I)
PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    re.S,
)
CREDENTIAL_VALUE = re.compile(
    rf"(?i)({_KEY_PREFIX}{_KEYWORD}{_KEY_SUFFIX}\s*[=:]\s*)"
    # "Authorization: Bearer <token>" / "Authorization: Basic <b64>" put the
    # scheme word before the actual credential; consume it too so the whole
    # credential is captured instead of stopping at the scheme word.
    r"(?:(?:Bearer|Basic)\s+)?[^\s,;]+"
)
IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
IPV6_CANDIDATE = re.compile(
    r"(?<![0-9A-Fa-f:])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![0-9A-Fa-f:])"
)
ABSOLUTE_PATH = re.compile(r"(?<![\w.])/(?:[A-Za-z0-9._-]+/)+[A-Za-z0-9._-]+")


class CollectionError(RuntimeError):
    """Raised when an allowlisted fact cannot be collected safely."""


class SecretScanError(RuntimeError):
    """Raised when staged or archived output contains a possible secret."""


class Aliases:
    def __init__(self) -> None:
        self._values: dict[str, dict[str, str]] = {}

    def get(self, category: str, value: Any) -> str:
        text = str(value)
        values = self._values.setdefault(category, {})
        if text not in values:
            values[text] = f"{category.upper()}_{len(values) + 1}"
        return values[text]


# Public alias so external tooling (e.g. the cross-repo redaction-conformance
# harness) can construct a real pseudonymizer by the same name the other two
# collectors expose, instead of falling back to a plain dict that silently
# skips pseudonymization.


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _safe_url(value: str) -> str:
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return value
    hostname = parsed.hostname or ""
    if parsed.port:
        hostname = f"{hostname}:{parsed.port}"
    return urlunsplit((parsed.scheme, hostname, parsed.path, parsed.query, parsed.fragment))


def _pseudonymize_ipv6(match: "re.Match[str]", aliases: Aliases) -> str:
    candidate = match.group()
    try:
        address = ipaddress.ip_address(candidate)
    except ValueError:
        return candidate
    if address.version != 6:
        return candidate
    return aliases.get("host", candidate)


def redact_text(text: str, aliases: Aliases) -> tuple[str, list[str]]:
    applied: set[str] = set()
    if PRIVATE_KEY_BLOCK.search(text):
        text = PRIVATE_KEY_BLOCK.sub("[REDACTED:private_key]", text)
        applied.add("private_key")
    if URL_USERINFO.search(text):
        text = URL_USERINFO.sub(r"\1[REDACTED:url_userinfo]@", text)
        applied.add("url_userinfo")
    if CREDENTIAL_VALUE.search(text):
        # "secret" matches the name both sibling collectors use for this class,
        # so one support engineer reading three bundles sees one vocabulary.
        text = CREDENTIAL_VALUE.sub(r"\1[REDACTED:secret]", text)
        applied.add("secret")

    lines = []
    for line in text.splitlines():
        lowered = line.lower()
        if "security" in lowered and (" rf" in lowered or "rf " in lowered):
            lines.append("[REDACTED:security_rf]")
            applied.add("security_rf")
            continue
        if "serial" in lowered:
            lines.append("[REDACTED:hardware_serial]")
            applied.add("hardware_serial")
            continue
        line = IPV4.sub(lambda match: aliases.get("host", match.group()), line)
        line = IPV6_CANDIDATE.sub(lambda match: _pseudonymize_ipv6(match, aliases), line)
        line = ABSOLUTE_PATH.sub(lambda match: aliases.get("path", match.group()), line)
        lines.append(line)
    suffix = "\n" if text.endswith("\n") else ""
    return "\n".join(lines) + suffix, sorted(applied)


def bound_log(text: str, line_limit: int, aliases: Aliases) -> tuple[str, list[str]]:
    lines = text.splitlines()[-line_limit:]
    bounded = "\n".join(lines)
    encoded = bounded.encode()
    truncated = len(encoded) > MAX_LOG_BYTES
    if truncated:
        bounded = encoded[-MAX_LOG_BYTES:].decode(errors="replace")
        bounded = "[log truncated to final 131072 bytes]\n" + bounded
    redacted, applied = redact_text(bounded + ("\n" if lines else ""), aliases)
    if truncated:
        applied = sorted(set(applied) | {"size_limit"})
    return redacted, applied


def scan_bytes(name: str, data: bytes) -> list[str]:
    findings: list[str] = []
    if FORBIDDEN_FILENAME.search(name):
        findings.append("forbidden_filename")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return findings + ["binary_content"]
    for rule, pattern in SECRET_PATTERNS.items():
        if pattern.search(text):
            findings.append(rule)
    for match in HIGH_ENTROPY_CANDIDATE.finditer(text):
        candidate = match.group()
        if candidate.startswith("[REDACTED:"):
            continue
        if re.fullmatch(r"[0-9a-fA-F]+", candidate):
            continue
        if len(set(candidate)) >= 12:
            findings.append("high_entropy_candidate")
            break
    return sorted(set(findings))


def scan_archive(path: Path) -> list[dict[str, Any]]:
    findings = []
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                if member.issym() or member.islnk():
                    findings.append({"path": member.name, "classes": ["archive_link"]})
                continue
            file_object = archive.extractfile(member)
            if file_object is None:
                findings.append({"path": member.name, "classes": ["unreadable_member"]})
                continue
            classes = scan_bytes(member.name, file_object.read())
            if classes:
                findings.append({"path": member.name, "classes": classes})
    return findings


class BundleBuilder:
    def __init__(
        self,
        output: Path,
        repository_sha: str,
        created_at: str | None = None,
        bundle_id: str | None = None,
    ) -> None:
        self.output = output
        self.aliases = Aliases()
        self.created_at = created_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self.bundle_id = bundle_id or str(uuid.uuid4())
        self.repository_sha = repository_sha
        self.components: list[dict[str, Any]] = []
        self.entries: list[dict[str, Any]] = []
        self.files: dict[str, bytes] = {}

    def add_json(
        self,
        logical_name: str,
        path: str,
        value: Any,
        category: str,
        sensitivity: str,
        command: str,
        redactions: list[str] | None = None,
    ) -> None:
        self._add(
            logical_name,
            path,
            _json_bytes(value),
            category,
            sensitivity,
            "application/json",
            command,
            redactions or [],
        )

    def add_text(
        self,
        logical_name: str,
        path: str,
        value: str,
        category: str,
        sensitivity: str,
        command: str,
        redactions: list[str] | None = None,
    ) -> None:
        self._add(
            logical_name,
            path,
            value.encode(),
            category,
            sensitivity,
            "text/plain",
            command,
            redactions or [],
        )

    def _add(
        self,
        logical_name: str,
        path: str,
        data: bytes,
        category: str,
        sensitivity: str,
        media_type: str,
        command: str,
        redactions: list[str],
    ) -> None:
        if path.startswith("/") or ".." in Path(path).parts:
            raise CollectionError(f"unsafe bundle path: {path}")
        if len(data) > MAX_TEXT_BYTES:
            raise CollectionError(f"{logical_name} exceeds the collection size limit")
        self.files[path] = data
        self.entries.append(
            {
                "logical_name": logical_name,
                "repository_owner": "mochad-docker",
                "category": category,
                "collection_command": command,
                "status": "collected",
                "path": path,
                "media_type": media_type,
                "size": len(data),
                "sha256": _sha256(data),
                "sensitivity": sensitivity,
                "redactions": sorted(set(redactions)),
                "reason": None,
            }
        )

    def omit(self, logical_name: str, category: str, reason: str) -> None:
        self.entries.append(
            {
                "logical_name": logical_name,
                "repository_owner": "mochad-docker",
                "category": category,
                "collection_command": None,
                "status": "omitted",
                "path": None,
                "media_type": None,
                "size": 0,
                "sha256": None,
                "sensitivity": "operational",
                "redactions": [],
                "reason": reason,
            }
        )

    def write(self) -> Path:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        output_name_findings = scan_bytes(self.output.name, b"")
        if output_name_findings:
            raise SecretScanError(
                f"output filename: {', '.join(output_name_findings)}"
            )
        staged_findings = [
            {"path": path, "classes": classes}
            for path, data in self.files.items()
            if (classes := scan_bytes(path, data))
        ]
        if staged_findings:
            raise SecretScanError(_finding_summary(staged_findings))

        ruleset = _sha256(
            "\n".join(
                [
                    *(f"{name}:{pattern.pattern}" for name, pattern in sorted(SECRET_PATTERNS.items())),
                    f"filename:{FORBIDDEN_FILENAME.pattern}",
                    f"high_entropy:{HIGH_ENTROPY_CANDIDATE.pattern}",
                    "binary:reject",
                ]
            ).encode()
        )
        scan_result = {
            "scanner": "mochad-docker-stdlib-scanner",
            "version": GENERATOR_VERSION,
            "rule_set_sha256": ruleset,
            "files_scanned": len(self.files) + 2,
            "findings_by_class": {},
            "unresolved_findings": 0,
            "archive_scanned": False,
            "status": "PASS",
        }
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "bundle_id": self.bundle_id,
            "created_at": self.created_at,
            "generator": {
                "name": "mochad-docker-support-bundle",
                "version": GENERATOR_VERSION,
                "repository_sha": self.repository_sha,
                "rule_set_sha256": ruleset,
            },
            "components": self.components,
            "redaction": {
                "replacement": "[REDACTED:<class>]",
                "pseudonymized_classes": [
                    "container",
                    "device",
                    "group",
                    "host",
                    "path",
                    "service",
                    "user",
                ],
            },
            "entries": self.entries,
            "secret_scan": scan_result,
        }
        manifest_bytes = _json_bytes(manifest)
        scan_result_bytes = _json_bytes(scan_result)
        for name, data in (
            ("manifest.json", manifest_bytes),
            ("scan-result.json", scan_result_bytes),
        ):
            findings = scan_bytes(name, data)
            if findings:
                raise SecretScanError(f"{name}: {', '.join(findings)}")

        with tempfile.TemporaryDirectory(prefix=".mochad-support-", dir=self.output.parent) as temp:
            stage = Path(temp)
            stage.chmod(0o700)
            staged_files = {
                **self.files,
                "manifest.json": manifest_bytes,
                "scan-result.json": scan_result_bytes,
            }
            for relative_path, data in staged_files.items():
                target = stage / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.parent.chmod(0o700)
                target.write_bytes(data)
                target.chmod(0o600)

            archive_file = tempfile.NamedTemporaryFile(
                prefix=".mochad-support-",
                suffix=".tar.gz",
                dir=self.output.parent,
                delete=False,
            )
            temporary_archive = Path(archive_file.name)
            archive_file.close()
            try:
                _create_archive(stage, temporary_archive)
                findings = scan_archive(temporary_archive)
                if findings:
                    raise SecretScanError(_finding_summary(findings))

                scan_result["archive_scanned"] = True
                for name, value in (
                    ("manifest.json", manifest),
                    ("scan-result.json", scan_result),
                ):
                    target = stage / name
                    target.write_bytes(_json_bytes(value))
                    target.chmod(0o600)
                _create_archive(stage, temporary_archive)
                findings = scan_archive(temporary_archive)
                if findings:
                    raise SecretScanError(_finding_summary(findings))
                os.replace(temporary_archive, self.output)
                self.output.chmod(0o600)
            finally:
                temporary_archive.unlink(missing_ok=True)
        return self.output


def _create_archive(stage: Path, output: Path) -> None:
    with tarfile.open(output, "w:gz") as archive:
        for path in sorted(stage.rglob("*")):
            archive.add(
                path,
                arcname=path.relative_to(stage),
                recursive=False,
                filter=_tar_filter,
            )


def _tar_filter(member: tarfile.TarInfo) -> tarfile.TarInfo:
    member.uid = member.gid = 0
    member.uname = member.gname = ""
    member.mode = 0o700 if member.isdir() else 0o600
    return member


def _finding_summary(findings: list[dict[str, Any]]) -> str:
    return "; ".join(f"{item['path']}: {', '.join(item['classes'])}" for item in findings)


class Docker:
    def run(self, *arguments: str) -> str:
        result = subprocess.run(
            ["docker", *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout

    def logs(self, container: str, lines: int) -> str:
        result = subprocess.run(
            ["docker", "logs", "--tail", str(lines), container],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout + result.stderr

    def format(self, image: str, template: str) -> Any:
        return json.loads(self.run("image", "inspect", "--format", template, image))


def collect_oci(docker: Docker, image: str) -> dict[str, Any]:
    labels = docker.format(image, "{{json .Config.Labels}}") or {}
    repo_digests = docker.format(image, "{{json .RepoDigests}}") or []
    return {
        "image_id": docker.format(image, "{{json .Id}}"),
        "digests": sorted({value.rsplit("@", 1)[-1] for value in repo_digests}),
        "os": docker.format(image, "{{json .Os}}"),
        "architecture": docker.format(image, "{{json .Architecture}}"),
        "entrypoint": docker.format(image, "{{json .Config.Entrypoint}}") or [],
        "command": docker.format(image, "{{json .Config.Cmd}}") or [],
        "labels": {
            key: _safe_url(str(value))
            for key, value in labels.items()
            if key in ALLOWED_OCI_LABELS
        },
    }


def collect_build_info(docker: Docker, image: str) -> dict[str, Any]:
    raw = docker.run(
        "run",
        "--rm",
        "--entrypoint",
        "cat",
        image,
        "/usr/share/mochad-docker/build-info.json",
    )
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise CollectionError("build-info.json is not a JSON object")
    return {
        key: _safe_url(str(item)) if "repository" in key or "image" in key else item
        for key, item in value.items()
        if key in ALLOWED_BUILD_INFO
    }


def sanitize_compose(value: dict[str, Any], aliases: Aliases) -> dict[str, Any]:
    services = value.get("services", {})
    if not isinstance(services, dict):
        raise CollectionError("rendered Compose services must be an object")
    sanitized = {"services": []}
    for name, service in sorted(services.items()):
        if not isinstance(service, dict):
            raise CollectionError(f"Compose service {name!r} must be an object")
        ports = []
        for port in service.get("ports", []):
            if isinstance(port, dict):
                ports.append(
                    {
                        "target": port.get("target"),
                        "protocol": port.get("protocol", "tcp"),
                    }
                )
        volumes = []
        for volume in service.get("volumes", []):
            if isinstance(volume, dict):
                volumes.append(
                    {
                        "type": volume.get("type"),
                        "target": volume.get("target"),
                        "read_only": bool(volume.get("read_only", False)),
                    }
                )
        environment = service.get("environment", {})
        if isinstance(environment, list):
            environment_keys = {str(item).split("=", 1)[0] for item in environment}
        elif isinstance(environment, dict):
            environment_keys = set(environment)
        else:
            environment_keys = set()
        sanitized["services"].append(
            {
                "name": aliases.get("service", name),
                "image": aliases.get("image", service["image"]) if service.get("image") else None,
                "build_configured": "build" in service,
                "ports": ports,
                "volumes": volumes,
                "device_cgroup_rules": len(service.get("device_cgroup_rules", [])),
                "cap_drop": sorted(service.get("cap_drop", [])),
                "security_options": len(service.get("security_opt", [])),
                "healthcheck_configured": "healthcheck" in service,
                "environment_keys": sorted(environment_keys & ALLOWED_ENVIRONMENT_KEYS),
            }
        )
    sanitized["network_count"] = len(value.get("networks", {}))
    sanitized["volume_count"] = len(value.get("volumes", {}))
    return sanitized


def collect_compose(docker: Docker, compose_file: Path, aliases: Aliases) -> dict[str, Any]:
    output = docker.run("compose", "-f", str(compose_file), "config", "--format", "json")
    value = json.loads(output)
    if not isinstance(value, dict):
        raise CollectionError("rendered Compose configuration is not a JSON object")
    return sanitize_compose(value, aliases)


def collect_runtime_identity(docker: Docker, container: str, aliases: Aliases) -> dict[str, Any]:
    uid = docker.run("exec", container, "id", "-u").strip()
    gid = docker.run("exec", container, "id", "-g").strip()
    groups = docker.run("exec", container, "id", "-G").split()
    return {
        "container": aliases.get("container", container),
        "uid": aliases.get("user", uid),
        "gid": aliases.get("group", gid),
        "supplementary_groups": sorted({aliases.get("group", item) for item in groups}),
    }


def collect_usb_permissions(path: Path, aliases: Aliases) -> dict[str, Any]:
    if not re.fullmatch(r"/dev/bus/usb/\d{3}/\d{3}", str(path)):
        raise CollectionError("USB paths must match /dev/bus/usb/NNN/NNN")
    details = path.lstat()
    if not stat.S_ISCHR(details.st_mode):
        raise CollectionError(f"{path} is not a character device")
    return {
        "device": aliases.get("device", path),
        "owner": aliases.get("user", details.st_uid),
        "group": aliases.get("group", details.st_gid),
        "mode": f"{stat.S_IMODE(details.st_mode):04o}",
        "major": os.major(details.st_rdev),
        "minor": os.minor(details.st_rdev),
    }


def repository_sha(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="Image to inspect")
    parser.add_argument("--output", type=Path, required=True, help="Output .tar.gz path")
    parser.add_argument("--container", help="Running container for identity and optional logs")
    parser.add_argument("--compose-file", type=Path, help="Compose file to render and sanitize")
    parser.add_argument(
        "--usb-device",
        type=Path,
        action="append",
        default=[],
        help="Explicit /dev/bus/usb/NNN/NNN node to inspect",
    )
    parser.add_argument("--include-logs", action="store_true", help="Include bounded container logs")
    parser.add_argument("--log-lines", type=int, default=200, help="Final log lines, maximum 1000")
    parser.add_argument("--dry-run", action="store_true", help="Print the collection plan only")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.log_lines <= MAX_LOG_LINES:
        raise SystemExit(f"--log-lines must be between 1 and {MAX_LOG_LINES}")
    if args.include_logs and not args.container:
        raise SystemExit("--include-logs requires --container")
    if args.dry_run:
        print(
            json.dumps(
                {
                    "image": "IMAGE_1",
                    "container": "CONTAINER_1" if args.container else None,
                    "compose": bool(args.compose_file),
                    "usb_devices": len(args.usb_device),
                    "logs": args.include_logs,
                    "output": str(args.output),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    root = Path(__file__).resolve().parents[2]
    builder = BundleBuilder(args.output, repository_sha(root))
    docker = Docker()
    try:
        oci = collect_oci(docker, args.image)
        builder.add_json(
            "oci-image-metadata",
            "image/oci.json",
            oci,
            "image",
            "public",
            "docker image inspect <IMAGE_1> using allowlisted fields",
        )
        build_info = collect_build_info(docker, args.image)
        builder.add_json(
            "build-information",
            "image/build-info.json",
            build_info,
            "image",
            "public",
            "read allowlisted build-info.json fields from <IMAGE_1>",
        )
        builder.components.append(
            {
                "repository": "mochad-docker",
                "version": oci["labels"].get("org.opencontainers.image.version"),
                "sha": oci["labels"].get("org.opencontainers.image.revision"),
                "ref": None,
                "dirty": None,
            }
        )
        builder.components.append(
            {
                "repository": "mochad-redux",
                "version": build_info.get("mochad_redux_version"),
                "sha": build_info.get("mochad_source_sha"),
                "ref": None,
                "dirty": None,
            }
        )

        if args.compose_file:
            builder.add_json(
                "compose-structure",
                "runtime/compose-structure.json",
                collect_compose(docker, args.compose_file, builder.aliases),
                "runtime",
                "operational",
                "docker compose -f <PATH_1> config --format json; allowlisted structure only",
                ["path", "service", "image"],
            )
        else:
            builder.omit("compose-structure", "runtime", "no Compose file was selected")

        if args.container:
            builder.add_json(
                "runtime-identity",
                "runtime/identity.json",
                collect_runtime_identity(docker, args.container, builder.aliases),
                "runtime",
                "operational",
                "id queries in <CONTAINER_1>",
                ["container", "user", "group"],
            )
        else:
            builder.omit("runtime-identity", "runtime", "no running container was selected")

        if args.usb_device:
            builder.add_json(
                "usb-permissions",
                "runtime/usb-permissions.json",
                [collect_usb_permissions(path, builder.aliases) for path in args.usb_device],
                "runtime",
                "operational",
                "lstat explicitly selected /dev/bus/usb nodes",
                ["device", "user", "group"],
            )
        else:
            builder.omit("usb-permissions", "runtime", "no USB device nodes were selected")

        if args.include_logs:
            logs, applied = bound_log(
                docker.logs(args.container, args.log_lines),
                args.log_lines,
                builder.aliases,
            )
            builder.add_text(
                "bounded-container-logs",
                "runtime/logs.txt",
                logs,
                "logs",
                "sensitive",
                f"docker logs --tail {args.log_lines} <CONTAINER_1>",
                applied,
            )
        else:
            builder.omit("bounded-container-logs", "logs", "logs were not explicitly requested")

        builder.write()
    except subprocess.CalledProcessError:
        print(
            "FAIL: an allowlisted Docker query failed; no support bundle was created",
            file=os.sys.stderr,
        )
        return 1
    except (CollectionError, SecretScanError, json.JSONDecodeError, OSError) as error:
        print(f"FAIL: support bundle was not created: {error}", file=os.sys.stderr)
        return 1

    print(f"PASS: support bundle created at {args.output}")
    print("Review the manifest and contents before sharing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
