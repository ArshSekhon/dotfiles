#!/usr/bin/env python3
"""Read-only inventory for planning a dotfiles installation (Python 3.8+)."""

import argparse
import json
import os
import platform
import pwd
import shutil
import subprocess
from pathlib import Path


TOOLS = {
    "chezmoi": ("chezmoi", "--version"),
    "zsh": ("zsh", "--version"),
    "tmux": ("tmux", "-V"),
    "tuicr": ("tuicr", "--version"),
    "nvim": ("nvim", "--version"),
    "git": ("git", "--version"),
    "ripgrep": ("rg", "--version"),
    "fzf": ("fzf", "--version"),
    "fd": ("fd", "--version"),
    "fdfind": ("fdfind", "--version"),
    "bat": ("bat", "--version"),
    "zoxide": ("zoxide", "--version"),
    "delta": ("delta", "--version"),
    "jq": ("jq", "--version"),
    "htop": ("htop", "--version"),
    "mise": ("mise", "--version"),
    "codex": ("codex", "--version"),
    "claude": ("claude", "--version"),
}
CONFIG_PATHS = (
    ".bashrc", ".bash_aliases", ".profile", ".zshenv", ".zprofile",
    ".zshrc", ".tmux.conf", ".config/nvim", ".config/tuicr", ".config/chezmoi",
)
LEGACY_LOADERS = {
    ".bash_aliases": "shell/ipad.sh",
    ".tmux.conf": "tmux/scrolling.conf",
}


def inspect_tool(command):
    executable = shutil.which(command[0])
    if executable is None:
        return {"installed": False}
    result = {"installed": True, "path": executable}
    try:
        completed = subprocess.run(
            [executable, *command[1:]], capture_output=True, text=True, timeout=15,
            stdin=subprocess.DEVNULL,
        )
        if completed.returncode != 0:
            result["error"] = "Version check exited with status {}".format(
                completed.returncode
            )
        else:
            lines = completed.stdout.splitlines() or completed.stderr.splitlines()
            result["version"] = lines[0] if lines else "No version output"
    except (OSError, subprocess.TimeoutExpired) as error:
        result["error"] = type(error).__name__
    return result


def inventory():
    user = pwd.getpwuid(os.getuid())
    home_dir = Path(user.pw_dir)
    report = {
        "os": platform.system(),
        "architecture": platform.machine(),
        "login_shell": user.pw_shell,
        "connection_markers": {
            key: bool(os.environ.get(key))
            for key in ("SSH_CONNECTION", "SSH_TTY", "TMUX")
        },
        "tools": {name: inspect_tool(command) for name, command in TOOLS.items()},
        "configuration": {},
        "legacy_loader_references": [],
    }
    if report["os"] == "Linux":
        try:
            for line in Path("/etc/os-release").read_text().splitlines():
                key, separator, value = line.partition("=")
                if separator and key in ("ID", "VERSION_ID", "PRETTY_NAME"):
                    report.setdefault("distribution", {})[key] = value.strip('"')
        except OSError:
            report["distribution"] = {"error": "Cannot read /etc/os-release"}
    elif report["os"] == "Darwin":
        report["macos_version"] = platform.mac_ver()[0]
    for relative in CONFIG_PATHS:
        path = home_dir / relative
        report["configuration"][relative] = (
            "symlink" if path.is_symlink() else "directory" if path.is_dir()
            else "file" if path.is_file() else "missing"
        )
    for relative, reference in LEGACY_LOADERS.items():
        try:
            if reference in (home_dir / relative).read_text(errors="replace"):
                report["legacy_loader_references"].append({
                    "file": relative, "reference": reference,
                })
        except OSError:
            pass
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print structured JSON")
    args = parser.parse_args()
    report = inventory()
    if args.json:
        print(json.dumps(report, indent=2))
        return
    distribution = report.get("distribution", {})
    print("OS:", distribution.get("PRETTY_NAME", report["os"]),
          report.get("macos_version", ""), report["architecture"])
    print("Login shell:", report["login_shell"])
    print("Connection markers:", report["connection_markers"])
    for name, tool in report["tools"].items():
        print("{}: {}".format(name, tool.get("version", tool.get("error", "missing"))))
        if "path" in tool:
            print("  Path:", tool["path"])
    for relative, kind in report["configuration"].items():
        print("Configuration: {} ({})".format(relative, kind))
    for loader in report["legacy_loader_references"]:
        print("Legacy loader: {} references {}".format(
            loader["file"], loader["reference"]
        ))


if __name__ == "__main__":
    main()
