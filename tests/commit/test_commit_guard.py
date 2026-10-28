import os
from pathlib import Path
import subprocess
import tempfile
import unittest


GUARD = Path(__file__).resolve().parents[2] / "skills" / "commit" / "scripts" / "commit-guard.py"


class CommitGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        self.env = os.environ.copy()
        for key in list(self.env):
            if key.startswith("GIT_"):
                del self.env[key]
        self.env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull})
        self.git(self.root, "init", "-q")
        self.git(self.root, "config", "user.name", "Test")
        self.git(self.root, "config", "user.email", "test@example.invalid")
        (self.root / "file.txt").write_text("initial\n")
        self.git(self.root, "add", "file.txt")
        self.git(self.root, "commit", "-qm", "Initial")

    def command(self, cwd, *args):
        return subprocess.run(args, cwd=cwd, env=self.env, capture_output=True, text=True)

    def git(self, cwd, *args):
        result = self.command(cwd, "git", *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def guard(self, cwd, message, *args):
        return self.command(cwd, "python3", str(GUARD), "--convention", "custom", "--message", message, *args)

    def commit_and_check(self, repo, cwd, message):
        (repo / "file.txt").write_text(message)
        self.git(repo, "add", "file.txt")
        result = self.guard(cwd, message)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git(repo, "log", "-1", "--format=%B").strip(), message)
        self.assertEqual(self.git(repo, "status", "--porcelain"), "")

    def test_root_subdirectory_and_linked_worktree(self):
        self.commit_and_check(self.root, self.root, "Root subject")
        subdir = self.root / "nested"
        subdir.mkdir()
        self.commit_and_check(self.root, subdir, "Nested subject\n\n본문 and body")
        worktree = Path(self.temp.name) / "worktree"
        self.git(self.root, "worktree", "add", "-qb", "test", str(worktree))
        self.commit_and_check(worktree, worktree, "Worktree subject\n\nBody")

    def test_submodule(self):
        parent = Path(self.temp.name) / "parent"
        parent.mkdir()
        self.git(parent, "init", "-q")
        self.git(parent, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(self.root), "child")
        child = parent / "child"
        self.git(child, "config", "user.name", "Test")
        self.git(child, "config", "user.email", "test@example.invalid")
        self.commit_and_check(child, child, "Submodule subject\n\nBody")

    def test_message_file(self):
        message_file = Path(self.temp.name) / "message.txt"
        message_file.write_text("File subject\n\nBody\n# ignored\n", encoding="utf-8")
        (self.root / "file.txt").write_text("changed")
        self.git(self.root, "add", "file.txt")
        result = self.command(
            self.root, "python3", str(GUARD), "--convention", "custom",
            "--file", str(message_file),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git(self.root, "log", "-1", "--format=%B").strip(), "File subject\n\nBody")

    def test_validation_dry_run_and_hook_failure(self):
        (self.root / "file.txt").write_text("staged")
        self.git(self.root, "add", "file.txt")
        before = self.git(self.root, "rev-parse", "HEAD")
        invalid = self.guard(self.root, "   ")
        self.assertEqual(invalid.returncode, 1)
        dry = self.guard(self.root, "Valid subject", "--dry-run")
        self.assertEqual(dry.returncode, 0, dry.stderr)
        hook = self.root / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        failure = self.guard(self.root, "Valid subject")
        self.assertNotEqual(failure.returncode, 0)
        self.assertEqual(self.git(self.root, "rev-parse", "HEAD"), before)
        self.assertEqual(self.git(self.root, "diff", "--cached", "--name-only").strip(), "file.txt")
        outside = self.guard(Path(self.temp.name), "Valid subject")
        self.assertNotEqual(outside.returncode, 0)
        self.assertIn("not a git repository", outside.stderr.lower())


if __name__ == "__main__":
    unittest.main()
