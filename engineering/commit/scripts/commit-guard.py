#!/usr/bin/env python3
import argparse
import re
import subprocess
import sys
from enum import Enum
from functools import lru_cache
from pathlib import Path


class Convention(str, Enum):
    CONVENTIONAL = "conventional"
    GITMOJI = "gitmoji"
    CUSTOM = "custom"


CONVENTION_CHOICES = tuple(item.value for item in Convention)
SCOPE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*$")
CONVENTIONAL_RE = re.compile(
    r"^(?P<type>[a-z]+)(?:\((?P<scope>[a-z0-9-]+)\))?(?P<breaking>!)?: (?P<subject>.+)$"
)
GITMOJI_CODE_RE = re.compile(r"^:([a-z0-9_+-]+):\s+(.+)$")
GITMOJI_SCOPE_RE = re.compile(r"^\(([^)]+)\):\s+(.+)$")
PAST_TENSE_STARTS = {
    "added",
    "built",
    "caught",
    "changed",
    "cleaned",
    "created",
    "dropped",
    "fixed",
    "improved",
    "made",
    "merged",
    "moved",
    "refactored",
    "removed",
    "renamed",
    "resolved",
    "reverted",
    "sent",
    "updated",
}


def read_message_from_file(path: Path) -> str:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ValueError(f"Message file not found: {path}")

    lines = []
    for line in content.splitlines():
        if line.startswith("#"):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).strip("\n")


def split_message(message: str):
    lines = message.splitlines()
    if not lines:
        return "", []
    subject = lines[0].strip()
    body = lines[1:]
    return subject, body


def has_body(body_lines):
    return any(line.strip() for line in body_lines)


def validate_blank_line(subject, body_lines):
    if has_body(body_lines):
        if not body_lines:
            return ["Body exists but could not be parsed."]
        if body_lines[0].strip() != "":
            return ["Leave one blank line between subject and body."]
    return []


def validate_body_wrap(body_lines):
    errors = []
    for i, line in enumerate(body_lines, start=2):
        if len(line) > 72:
            errors.append(f"Body line {i} exceeds 72 chars.")
    return errors


def validate_subject_length(subject):
    if len(subject) > 72:
        return ["Subject exceeds 72 chars."]
    return []


def validate_subject_period(subject):
    if subject.endswith("."):
        return ["Subject must not end with a period."]
    return []


def validate_subject_past_tense(subject):
    if not subject:
        return []
    first = subject.strip().split()[0].strip(".,:;!?)\"'").lower()
    if first in PAST_TENSE_STARTS:
        return ["Subject must not start with past tense."]
    return []


@lru_cache(maxsize=1)
def load_conventional_types():
    ref_path = (
        Path(__file__).resolve().parent.parent
        / "references"
        / "conventional-commits.md"
    )
    try:
        content = ref_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ValueError(f"Missing reference: {ref_path}")

    types = []
    in_section = False
    for line in content.splitlines():
        if line.startswith("## "):
            if in_section:
                break
            in_section = line.strip() == "## Allowed type list"
            continue
        if in_section:
            if match := re.match(r"- `([^`]+)`", line.strip()):
                types.append(match.group(1))
    if not types:
        raise ValueError("Failed to parse conventional type list.")
    return set(types)


@lru_cache(maxsize=1)
def load_gitmoji_allowlist():
    ref_path = Path(__file__).resolve().parent.parent / "references" / "gitmoji.md"
    try:
        content = ref_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ValueError(f"Missing reference: {ref_path}")

    emojis = set()
    codes = set()
    for line in content.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        if cells[0].lower() == "emoji" and cells[1].lower() == "code":
            continue
        if cells[0].startswith("---"):
            continue
        emoji = cells[0].strip()
        code = cells[1].strip().strip("`")
        if emoji:
            emojis.add(emoji)
        if code:
            codes.add(code)
    if not emojis or not codes:
        raise ValueError("Failed to parse gitmoji allowlist.")
    return emojis, codes


def parse_gitmoji_prefix(subject, emojis, codes):
    for emoji in sorted(emojis, key=len, reverse=True):
        if subject.startswith(emoji + " "):
            return emoji, subject[len(emoji) + 1 :]

    if match := GITMOJI_CODE_RE.match(subject):
        return f":{match.group(1)}:", match.group(2)
    return None, None


def validate_conventional(message):
    errors = []
    subject, body_lines = split_message(message)
    if not subject:
        return ["Subject line is required."]

    match = CONVENTIONAL_RE.match(subject)
    if not match:
        return ["Subject must match: type(scope): subject"]

    allowed_types = load_conventional_types()
    commit_type = match.group("type")
    scope = match.group("scope")
    subject_text = match.group("subject").strip()

    if commit_type not in allowed_types:
        errors.append(f"Type '{commit_type}' is not in the allowed list.")

    if scope and not SCOPE_RE.match(scope):
        errors.append("Scope must be kebab-case.")

    errors += validate_subject_length(subject_text)
    errors += validate_subject_period(subject_text)
    errors += validate_subject_past_tense(subject_text)
    errors += validate_blank_line(subject, body_lines)
    errors += validate_body_wrap(body_lines)
    return errors


def validate_gitmoji(message):
    errors = []
    subject, body_lines = split_message(message)
    if not subject:
        return ["Subject line is required."]

    emojis, codes = load_gitmoji_allowlist()
    prefix, rest = parse_gitmoji_prefix(subject, emojis, codes)
    if not prefix:
        return ["Subject must start with an allowed emoji or :code:."]

    if prefix.startswith(":") and prefix not in codes:
        errors.append(f"Code '{prefix}' is not in the allowed list.")
    elif not prefix.startswith(":") and prefix not in emojis:
        errors.append(f"Emoji '{prefix}' is not in the allowed list.")

    scope = None
    subject_text = rest.strip()
    if subject_text.startswith("("):
        scope_match = GITMOJI_SCOPE_RE.match(subject_text)
        if not scope_match:
            errors.append("Scope format must be: (scope): Subject")
        else:
            scope = scope_match.group(1).strip()
            subject_text = scope_match.group(2).strip()

    if scope and not SCOPE_RE.match(scope):
        errors.append("Scope must be kebab-case.")

    if subject_text and subject_text[0].isalpha() and not subject_text[0].isupper():
        errors.append("Subject must start with a capital letter.")

    errors += validate_subject_length(subject_text)
    errors += validate_subject_period(subject_text)
    errors += validate_subject_past_tense(subject_text)
    errors += validate_body_wrap(body_lines)
    return errors


def validate_custom(message):
    subject, _ = split_message(message)
    if not subject:
        return ["Subject line is required."]
    return []


def run_git_commit(message):
    git_dir = Path(".git")
    if not git_dir.is_dir():
        raise RuntimeError("Not a git repository (missing .git).")

    if "\n" in message:
        tmp_path = git_dir / "COMMIT_EDITMSG"
        tmp_path.write_text(message, encoding="utf-8")
        subprocess.run(["git", "commit", "-F", str(tmp_path)], check=True)
        return
    subprocess.run(["git", "commit", "-m", message], check=True)


def main():
    parser = argparse.ArgumentParser(
        description="Validate commit messages against a convention."
    )
    parser.add_argument("--convention", required=True, choices=CONVENTION_CHOICES)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--message", help="Commit message string")
    group.add_argument("--file", type=Path, help="Path to commit message file")
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate only; do not run git commit"
    )
    args = parser.parse_args()

    try:
        if args.message:
            message = args.message.strip("\n")
        else:
            message = read_message_from_file(args.file)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    convention = Convention(args.convention)
    if convention is Convention.CONVENTIONAL:
        errors = validate_conventional(message)
    elif convention is Convention.GITMOJI:
        errors = validate_gitmoji(message)
    else:
        errors = validate_custom(message)

    if errors:
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    if not args.dry_run:
        try:
            run_git_commit(message)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        except subprocess.CalledProcessError as exc:
            return exc.returncode

    if args.dry_run:
        print("Dry run: commit not executed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
