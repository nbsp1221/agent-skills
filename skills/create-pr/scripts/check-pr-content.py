#!/usr/bin/env python3
"""Flag publication-safety candidates without echoing their values."""

from __future__ import annotations

import argparse
import getpass
import ipaddress
import re
import socket
import sys
from dataclasses import dataclass
from pathlib import Path


MAX_BODY_BYTES = 1_048_576


@dataclass(frozen=True, order=True)
class Finding:
    location: str
    line: int
    category: str


PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("PRIVATE_KEY", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    ("CREDENTIAL_URL", re.compile(r"[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s/@]+@", re.IGNORECASE)),
    ("GITHUB_TOKEN", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("AWS_ACCESS_KEY", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("SLACK_TOKEN", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    (
        "SECRET_ASSIGNMENT",
        re.compile(
            r"(?i)\b(?:password|passwd|api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret)\b\s*[:=]\s*[^\s<>{}\[\]]{4,}"
        ),
    ),
    ("UNIX_HOME_PATH", re.compile(r"(?<![A-Za-z0-9_.-])/(?:home|Users)/[^\s/]+(?:/[^\s`'\"<>]*)?")),
    ("WINDOWS_HOME_PATH", re.compile(r"(?i)\b[A-Z]:\\Users\\[^\s\\]+(?:\\[^\s`'\"<>]*)?")),
    ("INTERNAL_DOCUMENT", re.compile(r"(?<![A-Za-z0-9_.-])\.internal(?:/|\\)")),
    ("TEMP_PATH", re.compile(r"(?<![A-Za-z0-9_.-])(?:/tmp/|/private/tmp/|/var/folders/|/run/user/)")),
    ("EMAIL_ADDRESS", re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")),
    ("LOCAL_URL", re.compile(r"(?i)https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])(?::\d+)?")),
    ("INTERNAL_DOMAIN", re.compile(r"(?i)\b[A-Z0-9-]+(?:\.[A-Z0-9-]+)*\.(?:internal|local|lan|corp)\b")),
    (
        "INTERNAL_IDENTIFIER",
        re.compile(r"(?i)\b(?:session|sandbox|container|job)[ _-]?id\s*[:#=]\s*[A-Z0-9][A-Z0-9-]{3,}\b"),
    ),
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check a proposed pull request title and body for publication-safety candidates."
    )
    parser.add_argument("--title", required=True)
    parser.add_argument("--body-file", required=True, type=Path)
    return parser.parse_args()


def local_literal_patterns() -> tuple[tuple[str, re.Pattern[str]], ...]:
    candidates: list[tuple[str, str]] = []
    hostname = socket.gethostname().strip()
    fqdn = socket.getfqdn().strip()
    home = str(Path.home())
    working_directory = str(Path.cwd())
    username = getpass.getuser().strip()

    for category, value in (
        ("LOCAL_HOSTNAME", hostname),
        ("LOCAL_HOSTNAME", fqdn),
        ("LOCAL_HOME_PATH", home),
        ("LOCAL_WORKSPACE_PATH", working_directory),
    ):
        if value and value not in {"localhost", ".", "/"}:
            candidates.append((category, value))

    if username and len(username) >= 3:
        candidates.append(("LOCAL_SHELL_IDENTITY", f"{username}@"))

    unique: dict[tuple[str, str], None] = {}
    for item in candidates:
        unique[item] = None
    return tuple((category, re.compile(re.escape(value))) for category, value in unique)


def private_ip_findings(text: str, location: str, line_number: int) -> list[Finding]:
    findings: list[Finding] = []
    for candidate in re.findall(r"(?<![0-9.])(?:\d{1,3}\.){3}\d{1,3}(?![0-9.])", text):
        try:
            address = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if address.is_private or address.is_loopback or address.is_link_local:
            findings.append(Finding(location, line_number, "PRIVATE_IP"))
    return findings


def scan_line(text: str, location: str, line_number: int) -> list[Finding]:
    findings = [
        Finding(location, line_number, category)
        for category, pattern in (*PATTERNS, *local_literal_patterns())
        if pattern.search(text)
    ]
    findings.extend(private_ip_findings(text, location, line_number))
    return findings


def main() -> int:
    arguments = parse_arguments()
    try:
        body_size = arguments.body_file.stat().st_size
        if body_size > MAX_BODY_BYTES:
            print("publication-safety: body exceeds the 1 MiB inspection limit", file=sys.stderr)
            return 2
        body = arguments.body_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        print(f"publication-safety: unable to inspect body ({type(error).__name__})", file=sys.stderr)
        return 2

    findings = scan_line(arguments.title, "title", 1)
    for line_number, line in enumerate(body.splitlines(), start=1):
        findings.extend(scan_line(line, "body", line_number))

    unique_findings = sorted(set(findings))
    if not unique_findings:
        print("publication-safety: passed")
        return 0

    print(f"publication-safety: {len(unique_findings)} candidate(s) require review", file=sys.stderr)
    for finding in unique_findings:
        print(f"- {finding.location}:{finding.line}: {finding.category}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
