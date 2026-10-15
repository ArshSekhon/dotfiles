#!/usr/bin/env python3
"""Install native SSH clipboard tunnels for the shared Mac Mosh allowlist.

Run during bootstrap, after installing cc-clip and pngpaste. Does not deploy to
remote hosts or edit SSH config, agent settings, or shell startup files.
"""

import argparse
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PREFIX = "com.dotfiles.clipboard."


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("Run this installer on the local Mac, not the remote host.")
    home = Path.home()
    config = Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config")))
    allowlist = config / "dotfiles/mosh-hosts"
    hosts = {line.split("#", 1)[0].strip() for line in allowlist.read_text().splitlines()}
    hosts.discard("")
    if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", host) for host in hosts):
        parser.error("The allowlist accepts exact SSH hostnames, without patterns or flags.")
    agents = home / "Library/LaunchAgents"
    desired = {}
    for host in sorted(hosts):
        label = PREFIX + host
        desired[agents / (label + ".plist")] = {
            "Label": label,
            "ProgramArguments": [
                "/usr/bin/ssh", "-NT", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
                "-o", "ExitOnForwardFailure=yes", "-o", "ServerAliveInterval=15",
                "-o", "ServerAliveCountMax=3", "-o", "ControlMaster=no", "-o", "ControlPath=none",
                "-R", "127.0.0.1:18339:127.0.0.1:18339", host,
            ],
            "RunAtLoad": True, "KeepAlive": True, "ThrottleInterval": 10,
            "StandardErrorPath": str(home / "Library/Logs" / (label + ".log")),
            "DotfilesClipboardTunnel": True,
        }
    stale = []
    for path in desired:
        if path.exists() and not plistlib.loads(path.read_bytes()).get("DotfilesClipboardTunnel"):
            parser.error("Refusing to replace a LaunchAgent not owned by dotfiles: " + str(path))
    for path in agents.glob(PREFIX + "*.plist"):
        if path not in desired and plistlib.loads(path.read_bytes()).get("DotfilesClipboardTunnel"):
            stale.append(path)
    changed = [path for path, data in desired.items()
               if not path.exists() or path.read_bytes() != plistlib.dumps(data)]
    print(json.dumps({"hosts": sorted(hosts), "write": [str(p) for p in changed],
                      "remove": [str(p) for p in stale], "dry_run": args.dry_run}, indent=2))
    if args.dry_run:
        return
    cc_clip = shutil.which("cc-clip")
    if not cc_clip or not shutil.which("pngpaste"):
        parser.error("Install cc-clip and pngpaste before installing clipboard tunnels.")
    domain = "gui/" + str(os.getuid())
    def loaded(label):
        return subprocess.run(["launchctl", "print", domain + "/" + label],
                              check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    if not loaded("com.cc-clip.daemon"):
        subprocess.run([cc_clip, "service", "install"], check=True)
    agents.mkdir(parents=True, exist_ok=True)
    (home / "Library/Logs").mkdir(parents=True, exist_ok=True)
    if changed or stale:
        state = Path(os.environ.get("XDG_STATE_HOME", str(home / ".local/state")))
        backup = state / "dotfiles/backups" / ("clipboard-tunnels-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
        backup.mkdir(parents=True, mode=0o700)
        manifest = []
        for path in changed + stale:
            previous = path.exists()
            if previous:
                shutil.copy2(path, backup / path.name)
            manifest.append({"path": str(path), "existed": previous})
            if loaded(path.stem):
                subprocess.run(["launchctl", "bootout", domain + "/" + path.stem], check=True)
        (backup / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        print("Backup:", backup)
    for path in stale:
        path.unlink()
    for path in changed:
        path.write_bytes(plistlib.dumps(desired[path]))
        path.chmod(0o600)
    for path in desired:
        if not loaded(path.stem):
            subprocess.run(["launchctl", "bootstrap", domain, str(path)], check=True)


if __name__ == "__main__":
    main()
