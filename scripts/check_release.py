"""Reject private files and common credential patterns in release archives."""

from __future__ import annotations

import argparse
import fnmatch
import re
import tarfile
import zipfile
from collections.abc import Iterator
from pathlib import Path, PurePosixPath

PRIVATE_NAMES = (
    ".env", ".env.*", ".envrc", ".pypirc", ".netrc", "_debug_msg.txt",
    "credentials*.json", "secrets*.json", "*.jsonl", "*.log", "*.pem", "*.key",
    "*.crt", "*.cer", "*.p12", "*.pfx", "*.flow", "*.pyc", ".DS_Store",
)
PRIVATE_DIRECTORIES = {".git", ".venv", "venv", "env", ".vscode", "data", "__pycache__"}
TOKEN_PATTERN = re.compile(
    r"pypi-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"
    r"|-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"
)
SECRET_ASSIGNMENT = re.compile(
    r"\b(?:SFX_TOKEN|WEBHOOK_SHARED_SECRET|TWINE_PASSWORD|NGROK_AUTHTOKEN)\s*=\s*([^\r\n]*)"
)


def private_path(name: str) -> bool:
    path = PurePosixPath(name)
    if any(part in PRIVATE_DIRECTORIES for part in path.parts):
        return True
    if path.name == ".env.example":
        return False
    return any(fnmatch.fnmatch(path.name, pattern) for pattern in PRIVATE_NAMES)


def contains_credential(content: bytes) -> bool:
    text = content.decode("utf-8", errors="replace")
    if TOKEN_PATTERN.search(text):
        return True
    for match in SECRET_ASSIGNMENT.finditer(text):
        value = match.group(1).split("#", 1)[0].strip().strip("'\"")
        if re.fullmatch(r"[A-Za-z0-9_-]{12,}", value) and not value.startswith(("YOUR_", "EXAMPLE_")):
            return True
    return False


def archive_files(path: Path) -> Iterator[tuple[str, bytes]]:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if not name.endswith("/"):
                    yield name, archive.read(name)
    elif path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as archive:
            for member in archive.getmembers():
                if member.issym() or member.islnk():
                    raise ValueError("Release archive contains a link")
                if member.isfile():
                    stream = archive.extractfile(member)
                    if stream is not None:
                        with stream:
                            yield member.name, stream.read()
    else:
        raise ValueError("Expected a .whl or .tar.gz release archive")


def check_archives(paths: list[Path]) -> list[str]:
    issues = []
    for path in paths:
        for name, content in archive_files(path):
            if private_path(name):
                issues.append(f"{path.name}: private file: {name}")
            if contains_credential(content):
                issues.append(f"{path.name}: possible credential in: {name}")
            if PurePosixPath(name).name == ".env.example":
                for line in content.decode("utf-8").splitlines():
                    key, separator, value = line.partition("=")
                    if key.strip() in {"SFX_TOKEN", "WEBHOOK_SHARED_SECRET"} and separator and value.strip():
                        issues.append(f"{path.name}: example configuration must have blank secrets: {name}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="*", type=Path, help="default: wheels and source archives in dist/")
    args = parser.parse_args()
    paths = args.archives or sorted([*Path("dist").glob("*.whl"), *Path("dist").glob("*.tar.gz")])
    if not paths:
        parser.error("No release archives found; run python -m build first")
    issues = check_archives(paths)
    for issue in issues:
        print(issue)
    if issues:
        return 1
    print(f"Checked {len(paths)} release archive(s): no private paths or recognized credentials found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
