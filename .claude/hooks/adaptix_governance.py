from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path.cwd()
PROTECTED_BRANCHES = {"main", "master"}
LOCAL_COMMAND_TIMEOUT_SECONDS = 0.2


def run(*args: str) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            list(args),
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=LOCAL_COMMAND_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 124, "", ""
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def event_name(payload: dict[str, Any]) -> str:
    for key in ("hook_event_name", "hookEventName", "eventName"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return "Unknown"


def block(message: str) -> int:
    sys.stderr.write(message.rstrip() + "\n")
    return 2


def git_repo() -> bool | None:
    code, out, _ = run("git", "rev-parse", "--is-inside-work-tree")
    if code == 0:
        return out == "true"
    if code == 128:
        return False
    return None


def current_branch() -> str | None:
    code, out, _ = run("git", "symbolic-ref", "--quiet", "--short", "HEAD")
    if code == 0:
        return out
    if code == 1:
        return ""
    return None


def working_tree_changes() -> list[str]:
    code, out, _ = run("git", "status", "--porcelain=v1")
    if code != 0:
        return ["<unable to inspect working tree>"]
    if not out:
        return []
    return [line for line in out.splitlines() if line.strip()]


def upstream_state() -> tuple[int, int] | None:
    code, out, _ = run(
        "git", "rev-list", "--left-right", "--count", "HEAD...@{upstream}"
    )
    if code != 0:
        return None
    parts = out.split()
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def default_remote_branch() -> str | None:
    code, out, _ = run(
        "git", "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"
    )
    if code == 0 and out:
        return out
    for candidate in ("origin/main", "origin/master"):
        code, _, _ = run("git", "rev-parse", "--verify", candidate)
        if code == 0:
            return candidate
    return None


def branch_integrated() -> bool:
    remote_default = default_remote_branch()
    if not remote_default:
        return False
    code, _, _ = run("git", "merge-base", "--is-ancestor", "HEAD", remote_default)
    return code == 0


def completion_gate() -> str:
    repo_state = git_repo()
    if repo_state is False:
        return ""
    if repo_state is None:
        return "AdaptixCore completion blocked: unable to verify Git repository state within the local hook time bound. Retry from a responsive checkout before stopping."

    changed = working_tree_changes()
    if changed:
        sample = "; ".join(changed[:6])
        return (
            "AdaptixCore completion blocked: working-tree task changes remain "
            f"({sample}). Commit, intentionally remove, or otherwise resolve them before stopping."
        )

    branch = current_branch()
    if branch is None:
        return "AdaptixCore completion blocked: unable to determine the current branch within the local hook time bound. Retry from a responsive repository before stopping."
    if not branch:
        return "AdaptixCore completion blocked: detached HEAD. Return to the active task branch or canonical branch before stopping."

    upstream = upstream_state()
    if upstream is not None:
        ahead, behind = upstream
        if ahead > 0:
            return f"AdaptixCore completion blocked: branch '{branch}' has {ahead} unpushed commit(s). Push the active task before stopping."
        if branch in PROTECTED_BRANCHES and behind > 0:
            return f"AdaptixCore completion blocked: protected branch '{branch}' is behind upstream by {behind} commit(s). Update it before stopping."
    elif branch in PROTECTED_BRANCHES:
        return f"AdaptixCore completion blocked: protected branch '{branch}' has no verifiable upstream state. Restore upstream tracking before stopping."

    if branch not in PROTECTED_BRANCHES:
        if not branch_integrated():
            return f"AdaptixCore completion blocked: active task branch '{branch}' is not proven integrated into the canonical remote branch. Finish the PR lifecycle before stopping."
        return f"AdaptixCore completion blocked: task branch '{branch}' is integrated. Switch to the canonical branch and clean the completed task branch/worktree before stopping."

    return ""


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            payload = {}
    except json.JSONDecodeError:
        payload = {}

    event = event_name(payload)

    if event == "SessionStart":
        sys.stdout.write("AdaptixCore lifecycle active. Reuse active work and finish the branch/PR lifecycle before advancing.\n")
        return 0

    if event in {"Stop", "TaskCompleted", "TaskComplete"}:
        reason = completion_gate()
        if reason:
            return block(reason)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
