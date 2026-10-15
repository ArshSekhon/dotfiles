#!/usr/bin/env python3
"""Offline regression checks for the Mac SSH/Mosh connection boundary."""

import io
import os
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


class Terminal(io.StringIO):
    def isatty(self):
        return True


class Executed(Exception):
    pass


def check(platform, host, resolved, expected, *, terminal=True, mosh=True, allowlist=True):
    with tempfile.TemporaryDirectory() as temporary:
        config = Path(temporary)
        if allowlist:
            (config / "dotfiles").mkdir()
            (config / "dotfiles/mosh-hosts").write_text("# Exact matches only\ndevbox.home.arpa\n")
        namespace = runpy.run_path(str(ROOT / "home/dot_local/bin/executable_dotfiles-remote"))
        calls = []
        def execute(binary, argv, env):
            calls.append((binary, argv, env))
            raise Executed
        def which(binary):
            return "/mock/" + binary if binary != "mosh" or mosh else None
        with mock.patch.object(sys, "platform", platform), \
                mock.patch.object(sys, "argv", ["dotfiles-remote", host]), \
                mock.patch.object(sys, "stdin", Terminal() if terminal else io.StringIO()), \
                mock.patch.object(sys, "stdout", Terminal() if terminal else io.StringIO()), \
                mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config), "TERM": "xterm-ghostty"}), \
                mock.patch("shutil.which", side_effect=which), \
                mock.patch("subprocess.run", return_value=subprocess.CompletedProcess(
                    [], 0, "hostname " + resolved + "\n", "")) as resolve, \
                mock.patch("os.execvpe", side_effect=execute):
            try:
                namespace["main"]()
            except Executed:
                pass
        assert len(calls) == 1
        binary, argv, env = calls[0]
        assert binary == "/mock/" + expected, calls
        assert argv[-1] == host
        assert env["TERM"] == "xterm-256color"
        if platform != "darwin" or not terminal or not mosh:
            resolve.assert_not_called()


def main():
    check("darwin", "devbox.home.arpa", "devbox.home.arpa", "mosh")
    check("darwin", "devbox", "devbox.home.arpa", "mosh")
    check("darwin", "arsh@devbox", "devbox.home.arpa", "mosh")
    check("darwin", "other", "other.home.arpa", "ssh")
    check("darwin", "suffix", "devbox.home.arpa.example.com", "ssh")
    check("darwin", "devbox", "devbox.home.arpa", "ssh", terminal=False)
    check("darwin", "devbox", "devbox.home.arpa", "ssh", mosh=False)
    check("darwin", "devbox", "devbox.home.arpa", "ssh", allowlist=False)
    check("linux", "devbox", "devbox.home.arpa", "ssh")
    print("PASS: exact allowlist, aliases/users, other hosts, pipelines, missing Mosh/config and Linux SSH")


if __name__ == "__main__":
    main()
