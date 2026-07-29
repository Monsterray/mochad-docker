# Deployment Backup and Isolated Restore

The offline backup tool preserves Docker-packaging inputs only:

- `docker-compose.yml`;
- `release/versions.env`;
- an optional allowlisted, non-secret environment snapshot.

It never archives `.env` verbatim, credentials, images, containers, volumes,
logs, Docker configuration, or USB state. The archive is an **unsanitized
operational backup** and must remain private.

## Back Up

```sh
python3 scripts/backup/backup_restore.py backup \
  --source-root . \
  --environment-file .env \
  --output /private/backups/mochad-docker.tar.gz
```

Secret-named environment variables are omitted. Unknown variables are omitted.
Recognized private-key or URL credential material fails the backup.

## Validate and Restore

Dry-run inspection writes nothing and never invokes Docker:

```sh
python3 scripts/backup/backup_restore.py restore \
  /private/backups/mochad-docker.tar.gz \
  --target-root /tmp/mochad-docker-restore
```

After reviewing the plan, activate only inside the isolated root:

```sh
python3 scripts/backup/backup_restore.py restore \
  /private/backups/mochad-docker.tar.gz \
  --target-root /tmp/mochad-docker-restore \
  --apply
```

Different existing files require `--overwrite`. Files are checksum-verified,
staged, metadata-verified, and atomically replaced. A failed multi-file
activation rolls back already replaced files. Validate the restored Compose
configuration separately before using it in any deployment.
