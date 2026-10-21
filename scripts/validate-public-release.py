#!/usr/bin/env python3
"""Fail closed when a public release contains private state or credential material."""
from __future__ import annotations

import json
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
raw = subprocess.check_output(
    ["git", "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
)
paths = [ROOT / item.decode("utf-8") for item in raw.split(b"\0") if item]

errors: list[str] = []
state_suffixes = {".db", ".sqlite", ".sqlite3", ".wal", ".shm"}
private_names = {"wallet.json", "credentials.json", "cookies.json", "atlas-partner-state-pack.zip"}
personal_paths = (
    re.compile(r"/home/" + "hp" + r"(?:/|\b)", re.I),
    re.compile(r"C:\\Users\\" + "hp" + r"(?:\\|\b)", re.I),
)
pem = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
credential_prefix = re.compile(r"(?<![A-Za-z0-9])(?:gh[opsu]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,})")
literal_assignment = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|password|passwd|client[_-]?secret|mnemonic|seed[_-]?phrase|authorization)\b\s*[:=]\s*['\"]([^'\"]{8,})['\"]"
)
safe_markers = {"example", "placeholder", "dummy", "fake", "test", "redacted", "required", "blocked", "none"}

for path in paths:
    relative = path.relative_to(ROOT).as_posix()
    name = path.name.casefold()
    if name in private_names or path.suffix.casefold() in state_suffixes:
        errors.append(f"FORBIDDEN_STATE_FILE:{relative}")
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        errors.append(f"FORBIDDEN_ENV_FILE:{relative}")
    if any(part.casefold() in {"backups", "cache", "__pycache__", "node_modules"} for part in path.parts):
        errors.append(f"FORBIDDEN_RUNTIME_PATH:{relative}")
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        continue
    if pem.search(text):
        errors.append(f"PRIVATE_KEY_MATERIAL:{relative}")
    if credential_prefix.search(text):
        errors.append(f"CREDENTIAL_PREFIX:{relative}")
    for pattern in personal_paths:
        if pattern.search(text):
            errors.append(f"PERSONAL_PATH:{relative}")
            break
    for line_number, line in enumerate(text.splitlines(), 1):
        match = literal_assignment.search(line)
        if not match:
            continue
        value = match.group(2).casefold()
        if not any(marker in value for marker in safe_markers):
            errors.append(f"POSSIBLE_CREDENTIAL:{relative}:{line_number}:{match.group(1)}")

workflow_root = ROOT / "atlas-local" / "atlas-control" / "n8n-workflows"
for path in workflow_root.glob("*.json"):
    data = json.loads(path.read_text(encoding="utf-8"))
    stack = [data]
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            for key, child in value.items():
                if key.casefold() in {"credentials", "credential", "oauth", "authentication"} and child not in ({}, [], None, "", "CREDENTIAL_REQUIRED"):
                    errors.append(f"N8N_CREDENTIAL:{path.relative_to(ROOT).as_posix()}:{key}")
                stack.append(child)
        elif isinstance(value, list):
            stack.extend(value)

print(f"SCANNED_FILES={len(paths)}")
print(f"SECRET_FINDINGS={len(errors)}")
print("SQLITE_PUBLISHED=" + ("YES" if any("STATE_FILE" in item for item in errors) else "NO"))
for error in sorted(set(errors)):
    print(error)
raise SystemExit(1 if errors else 0)
