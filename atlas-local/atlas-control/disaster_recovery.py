"""Verified Atlas backup and isolated restore. Never mutates the source database."""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import sqlite3
from datetime import datetime, timezone


def sha256(path):
    digest = hashlib.sha256()
    with pathlib.Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def integrity(path):
    db = sqlite3.connect(path)
    try:
        return db.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        db.close()


def create_backup(source_db, supporting_files, destination):
    source_db = pathlib.Path(source_db).resolve()
    destination = pathlib.Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    database_copy = destination / "atlas.sqlite"
    source = sqlite3.connect(f"file:{source_db}?mode=ro", uri=True)
    target = sqlite3.connect(database_copy)
    try:
        source.backup(target)
    finally:
        target.close(); source.close()
    if integrity(database_copy) != "ok":
        raise RuntimeError("BACKUP_INTEGRITY_FAILED")
    files_dir = destination / "files"; files_dir.mkdir()
    copied = []
    for source_path in supporting_files:
        path = pathlib.Path(source_path).resolve()
        if path.is_file():
            output = files_dir / path.name
            shutil.copy2(path, output)
            copied.append({"name": path.name, "sha256": sha256(output)})
    manifest = {"created": datetime.now(timezone.utc).isoformat(), "source_database_name": source_db.name, "database_sha256": sha256(database_copy), "database_integrity": "ok", "files": copied}
    (destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def restore_backup(backup, destination):
    backup = pathlib.Path(backup).resolve(); destination = pathlib.Path(destination).resolve()
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    database = backup / "atlas.sqlite"
    if sha256(database) != manifest["database_sha256"] or integrity(database) != "ok":
        raise RuntimeError("BACKUP_VERIFICATION_FAILED")
    destination.mkdir(parents=True, exist_ok=False)
    restored = destination / "atlas.sqlite"
    shutil.copy2(database, restored)
    shutil.copytree(backup / "files", destination / "files")
    if integrity(restored) != "ok":
        raise RuntimeError("RESTORE_INTEGRITY_FAILED")
    return restored


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    backup = sub.add_parser("backup"); backup.add_argument("database"); backup.add_argument("destination"); backup.add_argument("files", nargs="*")
    restore = sub.add_parser("restore"); restore.add_argument("backup"); restore.add_argument("destination")
    args = parser.parse_args()
    if args.command == "backup":
        print(json.dumps(create_backup(args.database, args.files, args.destination), indent=2))
    else:
        print(restore_backup(args.backup, args.destination))
