#!/usr/bin/env python3
"""Back up and restore mochad-docker deployment inputs offline."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

SCHEMA_VERSION = 1
MAX_MEMBER_BYTES = 2 * 1024 * 1024
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
MODE_RE = re.compile(r"^0[0-7]{3}$")
SECRET_RE = re.compile(
    r"(?i)(password|passwd|token|authorization|credential|private[_-]?key|secret)"
)
URL_CREDENTIAL_RE = re.compile(
    rb"[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@",
    re.IGNORECASE,
)
PRIVATE_KEY_RE = re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----")
ALLOWED_ENV = frozenset(
    {
        "ALPINE_BASE_IMAGE",
        "ALPINE_DIGEST",
        "BUILD_DATE",
        "IMAGE_VERSION",
        "MOCHAD_ARGS",
        "MOCHAD_BIND",
        "MOCHAD_FOREGROUND",
        "MOCHAD_OPENREMOTE_ENABLED",
        "MOCHAD_OPENREMOTE_PORT",
        "MOCHAD_PORT",
        "MOCHAD_RAW_DATA",
        "MOCHAD_REDUX_REVISION",
        "MOCHAD_REDUX_VERSION",
        "MOCHAD_REF",
        "MOCHAD_REPOSITORY",
        "MOCHAD_SHOW_HELP",
        "MOCHAD_SHOW_VERSION",
        "MOCHAD_SOURCE_SHA",
        "MOCHAD_XML_ENABLED",
        "MOCHAD_XML_PORT",
        "PGID",
        "PUID",
        "REQUIRE_AUDITED_SOURCE",
        "TZ",
        "UMASK",
        "USB_DEBUG",
        "USB_GID",
        "VCS_REF",
    }
)
OWNED_FILES = (
    ("docker-compose.yml", True, 10, "deployment_topology"),
    ("release/versions.env", True, 20, "release_source_pins"),
)
SECRET_PLACEHOLDERS = (
    "Docker registry credentials",
    "private registry credentials",
    "operator-managed secret environment files",
)


class BackupError(RuntimeError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _repository_sha(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    value = result.stdout.strip()
    if not SHA_RE.fullmatch(value):
        raise BackupError("repository SHA must be 40 lowercase hexadecimal characters")
    return value


def _check_content(name: str, data: bytes) -> None:
    if b"\0" in data:
        raise BackupError(f"{name} contains binary data")
    if PRIVATE_KEY_RE.search(data) or URL_CREDENTIAL_RE.search(data):
        raise BackupError(f"{name} contains secret material")


def _environment_snapshot(path: Path) -> bytes:
    values: dict[str, str] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise BackupError(f"{path}:{number}: expected NAME=value")
        key, value = line.split("=", 1)
        key = key.strip()
        if SECRET_RE.search(key):
            continue
        if key not in ALLOWED_ENV:
            continue
        encoded = value.strip().encode()
        _check_content(f"{path}:{number}", encoded)
        values[key] = value.strip()
    return "".join(f"{key}={values[key]}\n" for key in sorted(values)).encode()


def _add(archive: tarfile.TarFile, name: str, data: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o600
    info.mtime = 0
    info.uid = info.gid = 0
    archive.addfile(info, io.BytesIO(data))


def create_backup(
    source_root: Path,
    output: Path,
    *,
    environment_file: Path | None = None,
    repository_sha: str | None = None,
) -> dict:
    source_root = source_root.resolve()
    output = output.resolve()
    if output.exists():
        raise BackupError(f"backup already exists: {output}")

    payloads: dict[str, bytes] = {}
    entries = []
    for relative, required, order, role in OWNED_FILES:
        source = source_root / relative
        if not source.exists():
            if required:
                raise BackupError(f"required deployment file is missing: {source}")
            continue
        if source.is_symlink() or not source.is_file():
            raise BackupError(f"deployment input must be a regular file: {source}")
        data = source.read_bytes()
        _check_content(relative, data)
        archive_path = f"files/{relative}"
        payloads[archive_path] = data
        entries.append(_entry(relative, archive_path, data, source.stat(), required, order, role))

    if environment_file is not None:
        data = _environment_snapshot(environment_file)
        archive_path = "files/deployment.env"
        payloads[archive_path] = data
        entries.append(
            _entry(
                "deployment.env",
                archive_path,
                data,
                environment_file.stat(),
                False,
                30,
                "allowlisted_non_secret_environment",
            )
        )

    sha = repository_sha or _repository_sha(source_root)
    if not SHA_RE.fullmatch(sha):
        raise BackupError("repository SHA must be 40 lowercase hexadecimal characters")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "backup_id": _sha((sha + "".join(item["sha256"] for item in entries)).encode())[:20],
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "classification": "UNSANITIZED OPERATIONAL BACKUP",
        "source": {
            "repository": "mochad-docker",
            "sha": sha,
            "version": (source_root / "VERSION").read_text(encoding="utf-8").strip(),
        },
        "compatibility_contract_versions": {"backup_manifest": SCHEMA_VERSION},
        "entries": entries,
        "external_secret_placeholders": [
            {"name": name, "value": None} for name in SECRET_PLACEHOLDERS
        ],
        "restore_prerequisites": [
            "Restore only to an isolated directory.",
            "Supply credentials separately.",
            "Validate Compose before using restored files.",
        ],
        "rollback": [
            "Keep pre-restore files until validation passes.",
            "Activation failure restores replaced files.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp.{os.getpid()}")
    try:
        with tarfile.open(temporary, "w:gz") as archive:
            _add(archive, "manifest.json", _json(manifest))
            for name, data in sorted(payloads.items()):
                _add(archive, name, data)
        temporary.chmod(0o600)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return manifest


def _entry(
    original: str,
    archive: str,
    data: bytes,
    metadata: os.stat_result,
    required: bool,
    order: int,
    role: str,
) -> dict:
    return {
        "logical_role": role,
        "owning_repository": "mochad-docker",
        "original_path": original,
        "archive_path": archive,
        "sha256": _sha(data),
        "owner": str(metadata.st_uid),
        "group": str(metadata.st_gid),
        "mode": f"0{stat.S_IMODE(metadata.st_mode):03o}",
        "required": required,
        "secret_classification": "non-secret",
        "restore_order": order,
        "stable_identity_role": role,
        "compatibility_constraints": {"backup_manifest": SCHEMA_VERSION},
    }


def _json(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def inspect_backup(path: Path) -> tuple[dict, dict[str, bytes]]:
    try:
        with tarfile.open(path, "r:gz") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            if len(names) != len(set(names)):
                raise BackupError("archive contains duplicate members")
            if "manifest.json" not in names:
                raise BackupError("archive is missing manifest.json")
            for member in members:
                pure = PurePosixPath(member.name)
                if (
                    pure.is_absolute()
                    or ".." in pure.parts
                    or not member.isfile()
                    or member.size > MAX_MEMBER_BYTES
                ):
                    raise BackupError(f"unsafe archive member: {member.name}")
            manifest = json.load(archive.extractfile("manifest.json"))
            entries = _validate_manifest(manifest)
            expected = {"manifest.json", *(entry["archive_path"] for entry in entries)}
            if set(names) != expected:
                raise BackupError("archive contains undeclared or missing members")
            payloads = {}
            for entry in entries:
                data = archive.extractfile(entry["archive_path"]).read()
                if _sha(data) != entry["sha256"]:
                    raise BackupError(f"checksum mismatch: {entry['original_path']}")
                _check_content(entry["original_path"], data)
                payloads[entry["archive_path"]] = data
            return manifest, payloads
    except (OSError, tarfile.TarError, json.JSONDecodeError) as exc:
        raise BackupError(f"cannot inspect backup: {exc}") from exc


def _validate_manifest(manifest: object) -> list[dict]:
    if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA_VERSION:
        raise BackupError("unsupported backup manifest")
    source = manifest.get("source")
    if not isinstance(source, dict) or source.get("repository") != "mochad-docker":
        raise BackupError("backup is not owned by mochad-docker")
    if not SHA_RE.fullmatch(str(source.get("sha", ""))):
        raise BackupError("invalid source SHA")
    compatibility = manifest.get("compatibility_contract_versions")
    if not isinstance(compatibility, dict) or compatibility.get("backup_manifest") != 1:
        raise BackupError("incompatible backup contract")
    placeholders = manifest.get("external_secret_placeholders")
    if (
        not isinstance(placeholders, list)
        or {
            item.get("name")
            for item in placeholders
            if isinstance(item, dict) and item.get("value") is None
        }
        != set(SECRET_PLACEHOLDERS)
    ):
        raise BackupError("external secret placeholders are missing or invalid")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise BackupError("manifest entries must be a list")
    allowed = {
        "docker-compose.yml": (True, 10),
        "release/versions.env": (True, 20),
        "deployment.env": (False, 30),
    }
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise BackupError("manifest entries must be objects")
        original = entry.get("original_path")
        if (
            original not in allowed
            or original in seen
            or entry.get("owning_repository") != "mochad-docker"
            or entry.get("archive_path") != f"files/{original}"
            or not HASH_RE.fullmatch(str(entry.get("sha256", "")))
            or not MODE_RE.fullmatch(str(entry.get("mode", "")))
            or not str(entry.get("owner", "")).isdigit()
            or not str(entry.get("group", "")).isdigit()
            or entry.get("required") is not allowed.get(original, (None, None))[0]
            or entry.get("restore_order") != allowed.get(original, (None, None))[1]
            or entry.get("secret_classification") != "non-secret"
        ):
            raise BackupError(f"invalid manifest entry: {original!r}")
        seen.add(original)
    if not {"docker-compose.yml", "release/versions.env"} <= seen:
        raise BackupError("required deployment entries are missing")
    return sorted(entries, key=lambda item: item["restore_order"])


def _apply_metadata(path: Path, entry: dict) -> None:
    uid = int(entry["owner"])
    gid = int(entry["group"])
    if (path.stat().st_uid, path.stat().st_gid) != (uid, gid):
        try:
            os.chown(path, uid, gid)
        except PermissionError as exc:
            raise BackupError(f"cannot restore owner {uid}:{gid} for {path}") from exc
    path.chmod(int(entry["mode"], 8))


def restore(
    archive: Path,
    target: Path,
    *,
    apply: bool = False,
    overwrite: bool = False,
) -> dict:
    manifest, payloads = inspect_backup(archive)
    root = target.resolve()
    if root == Path("/"):
        raise BackupError("target '/' is not isolated")
    plan = []
    for entry in _validate_manifest(manifest):
        destination = root / entry["original_path"]
        if not destination.resolve(strict=False).is_relative_to(root):
            raise BackupError("restore path escapes target")
        action = "create"
        if destination.exists():
            if destination.is_symlink() or not destination.is_file():
                raise BackupError(f"unsafe destination: {destination}")
            action = "unchanged" if _sha(destination.read_bytes()) == entry["sha256"] else "replace"
            if apply and action == "replace" and not overwrite:
                raise BackupError(f"{destination} differs; pass --overwrite")
        plan.append((entry, destination, action))
    public = [{"path": item[0]["original_path"], "action": item[2]} for item in plan]
    if not apply:
        return {"status": "PASS", "mode": "dry-run", "plan": public}

    stage = root / f".mochad-docker-restore-{manifest['backup_id']}"
    if stage.exists():
        raise BackupError(f"staging path exists: {stage}")
    activated = []
    rollback_failed = False
    rollback = stage / "rollback"
    try:
        for entry, destination, action in plan:
            if action == "unchanged":
                continue
            staged = stage / "payload" / entry["archive_path"]
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(payloads[entry["archive_path"]])
            _apply_metadata(staged, entry)
            if _sha(staged.read_bytes()) != entry["sha256"]:
                raise BackupError(f"staged checksum mismatch: {entry['original_path']}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            old = rollback / entry["archive_path"]
            old.parent.mkdir(parents=True, exist_ok=True)
            had_original = destination.exists()
            if had_original:
                os.replace(destination, old)
            activated.append((destination, old, had_original))
            os.replace(staged, destination)
        for entry, destination, _ in plan:
            if _sha(destination.read_bytes()) != entry["sha256"]:
                raise BackupError(f"activated checksum mismatch: {entry['original_path']}")
            metadata = destination.stat()
            if (
                stat.S_IMODE(metadata.st_mode) != int(entry["mode"], 8)
                or metadata.st_uid != int(entry["owner"])
                or metadata.st_gid != int(entry["group"])
            ):
                raise BackupError(f"activated metadata mismatch: {entry['original_path']}")
    except (OSError, BackupError) as exc:
        failures = []
        for destination, old, had_original in reversed(activated):
            try:
                destination.unlink(missing_ok=True)
                if had_original:
                    os.replace(old, destination)
            except OSError as rollback_error:
                failures.append(str(rollback_error))
        rollback_failed = bool(failures)
        detail = f"; rollback failed: {'; '.join(failures)}" if failures else ""
        raise BackupError(f"restore failed: {exc}{detail}") from exc
    finally:
        if stage.exists() and not rollback_failed:
            shutil.rmtree(stage)
    return {"status": "PASS", "mode": "apply", "plan": public}


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("backup")
    backup.add_argument("--source-root", type=Path, default=Path("."))
    backup.add_argument("--environment-file", type=Path)
    backup.add_argument("--output", type=Path, required=True)
    backup.add_argument("--repository-sha")
    restore_parser = commands.add_parser("restore")
    restore_parser.add_argument("archive", type=Path)
    restore_parser.add_argument("--target-root", type=Path, required=True)
    restore_parser.add_argument("--apply", action="store_true")
    restore_parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "backup":
            result = create_backup(
                args.source_root,
                args.output,
                environment_file=args.environment_file,
                repository_sha=args.repository_sha,
            )
            output = {"status": "PASS", "backup_id": result["backup_id"]}
        else:
            output = restore(
                args.archive,
                args.target_root,
                apply=args.apply,
                overwrite=args.overwrite,
            )
    except (BackupError, OSError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}))
        return 1
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
