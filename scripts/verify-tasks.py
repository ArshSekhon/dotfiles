#!/usr/bin/env python3
"""Verify task navigation using a private tmux server, real fzf and synthetic tools."""

import fcntl
import json
import os
from pathlib import Path
import pty
import runpy
import select
import shutil
import struct
import subprocess
import sys
import tempfile
import termios
import time
from unittest.mock import patch


def main():
    tmux, fzf = shutil.which("tmux"), shutil.which("fzf")
    if not tmux or not fzf:
        raise SystemExit("tmux and fzf are required")
    repo = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, str(repo / "scripts/sync-tmux-keys.py"), "--check"], check=True)
    master, client = None, None
    observer_master, observer = None, None
    output = bytearray()
    with tempfile.TemporaryDirectory(prefix="dotfiles-tasks-") as temporary:
        root = Path(temporary)
        home = root / "home ' quoted"
        tools = home / ".local/bin"
        tools.mkdir(parents=True)
        for name in ("tmux-tasks", "tmux-workspace", "tmux-review", "tmux-agent", "tmux-attention"):
            shutil.copyfile(repo / "home/dot_local/bin" / ("executable_" + name), tools / name)
            (tools / name).chmod(0o700)
        shutil.copyfile(repo / "home/dot_local/bin/tmux_keys.py", tools / "tmux_keys.py")
        for name, executable in (("tmux", tmux), ("fzf", fzf), ("python3", sys.executable), ("git", shutil.which("git"))):
            (tools / name).symlink_to(executable)
        source_folder = root / "source"
        target_folder = root / "project $(touch injected); #(touch injected) ' quoted"
        source_folder.mkdir()
        target_folder.mkdir()
        subprocess.run(["git", "init", "-q", str(target_folder)], check=True, env=dict(os.environ, HOME=str(home)))
        review_result = root / "review.json"
        socket = root / "server.sock"
        env = os.environ.copy()
        for key in ("TMUX", "TMUX_PANE", "BASH_ENV", "ENV", "FZF_DEFAULT_OPTS",
                    "FZF_DEFAULT_OPTS_FILE", "FZF_DEFAULT_COMMAND"):
            env.pop(key, None)
        env.update(HOME=str(home), PATH=str(tools), TERM="xterm-256color",
                   XDG_STATE_HOME=str(home / ".local/state"),
                   DOTFILES_REVIEW_RESULT=str(review_result))
        command = [tmux, "-S", str(socket)]

        def run(*args):
            result = subprocess.run(command + list(args), env=env, capture_output=True,
                                    text=True, timeout=5)
            if result.returncode:
                raise RuntimeError(result.stderr or "tmux failed")
            return result.stdout.rstrip("\n")

        def drain(duration=0.1):
            deadline = time.monotonic() + duration
            while master is not None and time.monotonic() < deadline:
                if select.select([master], [], [], 0.02)[0]:
                    try:
                        output.extend(os.read(master, 65536))
                        del output[:-10000]
                    except OSError:
                        return

        def wait_for(predicate):
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                if predicate():
                    return
                drain(0.03)
            raise AssertionError("Timed out; active: " + run("display-message", "-p", "#{session_id}:#{window_id}.#{pane_id}") + "; terminal tail: " + repr(bytes(output[-1600:])))

        def press(keys):
            os.write(master, keys)
            drain()

        def active_for(name):
            for line in run("list-clients", "-F", "#{client_name}\t#{session_id}:#{window_id}.#{pane_id}").splitlines():
                attached, target = line.split("\t")
                if attached == name:
                    return target
            raise AssertionError("Fixture client is no longer attached")

        def active():
            return active_for(client_name)

        def open_picker():
            output.clear()
            started = time.perf_counter()
            os.write(master, b"\x01g")
            wait_for(lambda: b"Alt+s shell" in output)
            return (time.perf_counter() - started) * 1000

        try:
            config = repo / "home/dot_tmux.conf"
            run("-f", str(config), "new-session", "-d", "-s", "source", "-n", "shell",
                "-c", str(source_folder), "-x", "120", "-y", "40", "/bin/sleep 120")
            run("set-option", "-g", "default-shell", "/bin/sh")
            run("set-option", "-g", "default-command", "/bin/sleep 120")
            source = run("display-message", "-p", "#{session_id}:#{window_id}.#{pane_id}")
            run("new-session", "-d", "-s", "project", "-n", "task-window",
                "-c", str(target_folder).replace("#", "##"), "/bin/sleep 120")
            target = run("display-message", "-p", "-t", "=project:",
                         "#{session_id}:#{window_id}.#{pane_id}")
            run("set-option", "-p", "-t", target, "@dotfiles_agent", "codex")
            run("set-option", "-p", "-t", target, "@dotfiles_pane_name", "review-task")
            other = run("split-window", "-d", "-t", target, "-c", str(target_folder).replace("#", "##"),
                        "-P", "-F", "#{session_id}:#{window_id}.#{pane_id}", "/bin/sleep 120")
            run("set-option", "-p", "-t", other, "@dotfiles_agent", "claude")
            run("set-option", "-p", "-t", other, "@dotfiles_pane_name", "other-task")
            run("select-pane", "-t", other)
            run("resize-pane", "-Z", "-t", other)
            # The same window linked into another session must retain its context.
            run("new-session", "-d", "-s", "linked", "/bin/sleep 120")
            run("link-window", "-s", "=project:1", "-t", "=linked:2")
            linked_target = run("display-message", "-p", "-t", "=linked:2.1",
                                "#{session_id}:#{window_id}.#{pane_id}")
            original = run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}").splitlines()
            master, slave = pty.openpty()
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
            client = subprocess.Popen(command + ["attach-session", "-t", "=source"],
                                      env=env, stdin=slave, stdout=slave, stderr=slave,
                                      start_new_session=True)
            os.close(slave)
            wait_for(lambda: run("list-clients", "-F", "#{client_name}"))
            client_name = run("list-clients", "-F", "#{client_name}")
            run("new-session", "-d", "-s", "observer", "/bin/sleep 120")
            observer_master, observer_slave = pty.openpty()
            fcntl.ioctl(observer_slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
            observer = subprocess.Popen(command + ["attach-session", "-t", "=observer"],
                                        env=env, stdin=observer_slave, stdout=observer_slave,
                                        stderr=observer_slave, start_new_session=True)
            os.close(observer_slave)
            wait_for(lambda: len(run("list-clients", "-F", "#{client_name}").splitlines()) == 2)
            observer_name = next(name for name in run("list-clients", "-F", "#{client_name}").splitlines() if name != client_name)
            observer_target = active_for(observer_name)
            drain(0.2)
            wait_for(lambda: run("display-message", "-p", "-t", target, "#{pane_current_path}") == str(target_folder))
            popup_ms = open_picker()
            press(b"\x1b")
            drain(0.25)
            assert active() == source
            press(b"\x01B")
            assert active() == source
            wait_for(lambda: "No previous task" in run("show-messages", "-t", client_name))
            with patch.dict(os.environ, env, clear=True):
                tasks = runpy.run_path(str(tools / "tmux-tasks"))
                started = time.perf_counter()
                panes = tasks["inventory"](run)
                inventory_ms = (time.perf_counter() - started) * 1000
                assert len(panes) == 7  # Two linked panes appear in both sessions, plus observer.
                assert tasks["safe_label"]("title\x1b]52;bad\x07") == "title?]52;bad?"
                try:
                    tasks["find_target"](run, "$999:@999.%999")
                except ValueError:
                    pass
                else:
                    raise AssertionError("Stale pane was accepted")
                missing = dict(panes[0], pane_current_path=str(root / "missing"))
                try:
                    tasks["working_folder"](missing)
                except ValueError:
                    pass
                else:
                    raise AssertionError("Missing folder was accepted")
                assert "exited" in tasks["row_label"](dict(panes[0], pane_dead="1"), source)
            # User fzf options must not add executable previews or remap Enter.
            run("set-environment", "-g", "FZF_DEFAULT_OPTS", "--bind=enter:abort --preview='touch injected'")
            open_picker()
            press(b"'project\\ / 'review-task\r")
            wait_for(lambda: active() == target)
            assert run("display-message", "-p", "-t", target, "#{window_zoomed_flag}") == "1"
            press(b"\x01B")
            wait_for(lambda: active() == source)
            press(b"\x01B")
            wait_for(lambda: active() == target)
            open_picker()
            press(b"'linked\\ / 'review-task\r")
            wait_for(lambda: active() == linked_target)
            press(b"\x01B")
            wait_for(lambda: active() == target)
            # The Workspace menu hands off to a larger task popup.
            output.clear()
            press(b"\x01N")
            wait_for(lambda: b"existing work" in output)
            press(b"g")
            wait_for(lambda: b"Alt+s shell" in output)
            press(b"\x1b")
            drain(0.25)
            assert active() == target
            # Missing review tools leave a useful message and create nothing.
            open_picker()
            press(b"'project\\ / 'review-task\x12")
            wait_for(lambda: b"Install tuicr" in output)
            press(b"\x1b")
            drain(0.25)
            (tools / "tuicr").write_text(
                "#!" + sys.executable + "\nimport json, os, sys\n"
                "with open(os.environ['DOTFILES_REVIEW_RESULT'], 'w') as stream:\n"
                "    json.dump({'cwd': os.getcwd(), 'args': sys.argv[1:]}, stream)\n")
            (tools / "tuicr").chmod(0o700)
            press(b"\x01B")
            source_before_review = active()
            open_picker()
            press(b"'project\\ / 'review-task\x12")
            wait_for(review_result.exists)
            assert json.loads(review_result.read_text()) == {"cwd": str(target_folder), "args": ["-w", "--stdout", "--no-update-check"]}, review_result.read_text()
            assert active() == source_before_review
            # Rename is label metadata; no process or window identity changes.
            open_picker()
            press(b"'project\\ / 'review-task\x1bn")
            wait_for(lambda: b"Name:" in output)
            press(b"renamed-task\r")
            wait_for(lambda: run("display-message", "-p", "-t", target,
                                 "#{@dotfiles_pane_name}") == "renamed-task")
            press(b"\x1b")
            drain(0.25)
            # Hide/unhide is reversible and works even when the query has no match.
            open_picker()
            press(b"'project\\ / 'renamed-task\x1ba")
            wait_for(lambda: run("display-message", "-p", "-t", target,
                                 "#{@dotfiles_task_archived}") == "1")
            press(b"\x1bh")
            wait_for(lambda: b"(shown)" in output)
            press(b"\x1ba")
            wait_for(lambda: run("display-message", "-p", "-t", target,
                                 "#{@dotfiles_task_archived}") == "0")
            press(b"\x1b")
            drain(0.25)
            # A shell uses the selected task's folder, not the invoking folder.
            open_picker()
            press(b"'project\\ / 'renamed-task\x1bs")
            wait_for(lambda: active() != source_before_review)
            shell_target = active()
            assert run("display-message", "-p", "-t", shell_target,
                       "#{pane_current_path}") == str(target_folder)
            assert run("display-message", "-p", "-t", shell_target, "#{@dotfiles_agent}") == ""
            assert run("display-message", "-p", "-t", shell_target, "#{@dotfiles_pane_name}") == "shell"
            assert run("display-message", "-p", "-t", target, "#{window_zoomed_flag}") == "1"
            press(b"\x01B")
            wait_for(lambda: active() == source_before_review)
            # Missing fzf reports visibly, without changing existing work.
            (tools / "fzf").unlink()
            output.clear()
            press(b"\x01g")
            wait_for(lambda: b"Install fzf separately" in output)
            press(b"\x1b")
            drain(0.25)
            (tools / "fzf").symlink_to(fzf)
            run("source-file", str(config))
            assert run("display-message", "-p", "-t", target, "#{@dotfiles_pane_name}") == "renamed-task"
            assert all(row in run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}").splitlines()
                       for row in original)
            assert active_for(observer_name) == observer_target
            assert (home / ".local/state/dotfiles/reviews").stat().st_mode & 0o777 == 0o700
            assert not list(root.rglob("injected"))
            report = {"checks": "passed", "task_popup_ready_ms": round(popup_ms, 1),
                      "inventory_ms": round(inventory_ms, 1), "panes_in_inventory": len(panes)}
            if sys.platform.startswith("linux"):
                # Include fzf and its helper while the popup is waiting for input.
                open_picker()
                server = int(run("display-message", "-p", "#{pid}"))
                def cpu_ticks():
                    processes = {}
                    for entry in Path("/proc").iterdir():
                        if not entry.name.isdigit():
                            continue
                        try:
                            stat = (entry / "stat").read_text().rsplit(")", 1)[1].split()
                            processes[int(entry.name)] = (int(stat[1]), int(stat[11]) + int(stat[12]))
                        except (OSError, ValueError, IndexError):
                            continue
                    descendants = {server}
                    while True:
                        expanded = descendants | {pid for pid, (parent, _) in processes.items() if parent in descendants}
                        if expanded == descendants:
                            break
                        descendants = expanded
                    return sum(processes[pid][1] for pid in descendants if pid in processes)
                before = cpu_ticks()
                started = time.monotonic()
                drain(1)
                report["idle_popup_cpu_percent_sample"] = round(
                    (cpu_ticks() - before) / os.sysconf("SC_CLK_TCK") / (time.monotonic() - started) * 100, 2)
                press(b"\x1b")
            drain(0.25)
            print(json.dumps(report, indent=2))
        finally:
            subprocess.run(command + ["kill-server"], env=env, capture_output=True, timeout=5)
            if client is not None:
                try:
                    client.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    client.terminate()
                    client.wait(timeout=2)
            if observer is not None:
                try:
                    observer.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    observer.terminate()
                    observer.wait(timeout=2)
            if observer_master is not None:
                os.close(observer_master)
            if master is not None:
                os.close(master)


if __name__ == "__main__":
    main()
