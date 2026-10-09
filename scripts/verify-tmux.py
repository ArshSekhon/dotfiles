#!/usr/bin/env python3
"""Exercise the tmux baseline on a private socket with a synthetic terminal."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import pty
import re
import runpy
import select
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fzf", default=shutil.which("fzf"), help="fzf executable for the isolated picker")
    args = parser.parse_args()
    if not args.fzf:
        raise SystemExit("fzf is required; use the agent bootstrap in BOOTSTRAP.md")
    fzf = str(Path(args.fzf).resolve())
    tmux = shutil.which("tmux")
    if not tmux:
        raise SystemExit("tmux is required")
    config = Path(__file__).resolve().parents[1] / "home/dot_tmux.conf"
    subprocess.run([sys.executable, str(config.parent.parent / "scripts/sync-tmux-keys.py"), "--check"], check=True)
    client = None
    master = None
    terminal_output = bytearray()
    with tempfile.TemporaryDirectory(prefix="dotfiles-tmux-") as directory:
        root = Path(directory)
        checkout = root / "project checkout"
        checkout.mkdir()
        tools = root / "bin tools"
        tools.mkdir()
        result_file = root / "review.json"
        socket = root / "tmux server.sock"
        fixture_home = root / "home (pilot),+"
        helper = fixture_home / ".local/bin/tmux-scratch"
        helper.parent.mkdir(parents=True)
        shutil.copyfile(config.parent / "dot_local/bin/executable_tmux-scratch", helper)
        helper.chmod(0o700)
        agent_helper = fixture_home / ".local/bin/tmux-workspace"
        shutil.copyfile(config.parent / "dot_local/bin/executable_tmux-workspace", agent_helper)
        agent_helper.chmod(0o700)
        recovery_helper = fixture_home / ".local/bin/tmux-agent"
        shutil.copyfile(config.parent / "dot_local/bin/executable_tmux-agent", recovery_helper)
        recovery_helper.chmod(0o700)
        for name in ("tmux-tasks", "tmux-review", "tmux-attention", "tmux-sessions"):
            shutil.copyfile(config.parent / ("dot_local/bin/executable_" + name), helper.parent / name)
            (helper.parent / name).chmod(0o700)
        shutil.copyfile(config.parent / "dot_local/bin/tmux_keys.py", helper.parent / "tmux_keys.py")
        subprocess.run(["git", "init", "-q", str(checkout)], check=True, env=dict(os.environ, HOME=str(fixture_home)))
        for name, executable in (("python3", sys.executable), ("tmux", tmux), ("fzf", fzf),
                                 ("git", shutil.which("git"))):
            if not executable:
                raise SystemExit(name + " is required")
            (tools / name).symlink_to(executable)
        home_folder = fixture_home / "Documents/My Folder"
        home_folder.mkdir(parents=True)
        (fixture_home / ".hidden-folder").mkdir()
        home_projects = fixture_home / "workspace"
        home_project = home_projects / "Absolute Project"
        home_project.mkdir(parents=True)
        (home_project / ".git").write_text("gitdir: fixture\n")
        literal_tilde = fixture_home / "Documents/Literal~Folder"
        literal_tilde.mkdir()
        scratch_root = root / "private scratch"
        projects = root / "projects"
        alpha = projects / "Alpha Project"
        beta = projects / "group/Beta Project"
        other_root = root / "other projects"
        other = other_root / "Other App"
        for project in (alpha, beta, other):
            project.mkdir(parents=True)
            (project / ".git").write_text("gitdir: fixture\n")
            (project / "src/internal").mkdir(parents=True)
        for excluded in ("node_modules/dependency", ".hidden/project", "too/deep/project"):
            (projects / excluded).mkdir(parents=True)
        outside = root / "outside"
        outside.mkdir()
        (projects / "external-link").symlink_to(outside, target_is_directory=True)
        env = os.environ.copy()
        for key in ("TMUX", "TMUX_PANE", "BASH_ENV", "ENV"):
            env.pop(key, None)
        env.update(
            PATH=str(tools),
            TERM="xterm-256color",
            DOTFILES_REVIEW_RESULT=str(result_file),
            HOME=str(fixture_home),
            XDG_CONFIG_HOME=str(fixture_home / ".config"),
            XDG_STATE_HOME=str(fixture_home / ".local/state"),
            XDG_DATA_HOME=str(fixture_home / ".local/share"),
            XDG_CACHE_HOME=str(fixture_home / ".cache"),
            DOTFILES_SCRATCH_ROOT=str(scratch_root),
            DOTFILES_PROJECT_ROOTS=os.pathsep.join(map(str, (projects, other_root, home_projects))),
        )
        with patch.dict(os.environ, env, clear=True):
            launcher = runpy.run_path(str(agent_helper))
            candidates_started = time.perf_counter()
            candidates = launcher["folder_candidates"](str(checkout))
            folder_candidates_ms = (time.perf_counter() - candidates_started) * 1000
            assert candidates[0] == str(checkout)
            assert all(str(project) in candidates for project in (alpha, beta, other))
            assert str(outside) not in candidates
            assert not any(part in p for p in candidates
                           for part in ("node_modules", ".hidden", "src/internal", "too/deep/project"))
            assert launcher["session_name_for"](str(alpha)) == "alpha-project"
            with patch.dict(os.environ, DOTFILES_PROJECT_ROOTS="relative"):
                try:
                    launcher["folder_candidates"](str(checkout))
                except ValueError:
                    pass
                else:
                    raise AssertionError("Relative project roots were accepted")
        command = [tmux, "-S", str(socket)]

        def run(*args):
            result = subprocess.run(
                command + list(args), env=env, capture_output=True, text=True,
                timeout=5,
            )
            if result.returncode or result.stderr:
                raise RuntimeError(result.stderr or "tmux command failed")
            return result.stdout.strip()

        def wait_for(predicate):
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                if predicate():
                    return
                drain(0.03)
            raise RuntimeError("Timed out waiting for tmux behavior; terminal tail: "
                               + repr(bytes(terminal_output[-1200:])))

        def drain(duration):
            deadline = time.monotonic() + duration
            while master is not None and time.monotonic() < deadline:
                if select.select([master], [], [], 0.02)[0]:
                    try:
                        output = os.read(master, 65536)
                        if not output:
                            return
                        terminal_output.extend(output)
                        del terminal_output[:-4000]
                    except OSError:
                        return

        def press(keys):
            os.write(master, keys)
            drain(0.15)

        try:
            started = time.perf_counter()
            run(
                "-f", str(config), "new-session", "-d", "-s", "baseline",
                "-n", "review", "-c", str(checkout), "-x", "120", "-y", "40",
                "/bin/sleep 120",
            )
            startup_ms = (time.perf_counter() - started) * 1000
            # New windows use a noninteractive fixture command, never user startup files.
            run("set-option", "-g", "default-shell", "/bin/sh")
            run("set-option", "-g", "default-command", "/bin/sleep 120")
            run("source-file", str(config))
            assert run("show-options", "-gv", "prefix") == "C-a"
            assert run("show-options", "-gwv", "mode-keys") == "vi"
            assert run("show-options", "-sv", "extended-keys") == "on"
            assert run("show-options", "-sv", "set-clipboard") == "on"
            assert run("show-options", "-gv", "status-position") == "bottom"
            assert run("display-message", "-p", "#{window_index}:#{pane_index}") == "1:1"
            bindings = run("list-keys", "-T", "prefix")
            assert not re.search(r"\bprefix\s+(C-x|C-u)\s", bindings)
            assert "--menu" in run("list-keys", "-T", "prefix", "N")
            assert "tmux-tasks" in run("list-keys", "-T", "prefix", "g")
            assert "--previous" in run("list-keys", "-T", "prefix", "B")
            assert "send-prefix" in run("list-keys", "-T", "prefix", "C-a")
            for option in ("status-left", "status-right", "pane-border-format"):
                assert "#(" not in run("show-options", "-gv", option)

            master, slave = pty.openpty()
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
            client = subprocess.Popen(
                command + ["attach-session", "-t", "baseline"], env=env,
                stdin=slave, stdout=slave, stderr=slave, start_new_session=True,
            )
            os.close(slave)
            wait_for(lambda: run("list-clients", "-F", "#{client_width}") == "120")
            client_name = run("list-clients", "-F", "#{client_name}")
            drain(0.3)

            press(b"\x01|")
            wait_for(lambda: len(run("list-panes").splitlines()) == 2)
            assert all(
                path == str(checkout)
                for path in run("list-panes", "-F", "#{pane_current_path}").splitlines()
            )
            press(b"\x01h")
            assert run("display-message", "-p", "#{pane_index}") == "1"
            press(b"\x01l")
            assert run("display-message", "-p", "#{pane_index}") == "2"
            press(b"\x01z")
            assert run("display-message", "-p", "#{window_zoomed_flag}") == "1"
            press(b"\x01z")
            press(b"\x01c")
            wait_for(lambda: len(run("list-windows").splitlines()) == 2)
            assert run("display-message", "-p", "#{pane_current_path}") == str(checkout)
            press(b"\x01\t")
            assert run("display-message", "-p", "#{window_index}") == "1"
            press(b"\x01\t")
            assert run("display-message", "-p", "#{window_index}") == "2"
            press(b"\x01\t")
            assert run("display-message", "-p", "#{window_index}") == "1"
            run("kill-window", "-t", "baseline:1")
            assert run("display-message", "-p", "#{window_index}") == "1"

            press(b"\x01r")
            wait_for(lambda: b"Install tuicr" in terminal_output)
            press(b"\x1b")
            drain(0.2)
            stub = tools / "tuicr"
            stub.write_text(
                "#!" + sys.executable + "\n"
                "import json, os, sys\n"
                "with open(os.environ['DOTFILES_REVIEW_RESULT'], 'w') as stream:\n"
                "    json.dump({'cwd': os.getcwd(), 'args': sys.argv[1:]}, stream)\n"
            )
            stub.chmod(0o700)
            press(b"\x01r")
            wait_for(result_file.exists)
            assert json.loads(result_file.read_text()) == {
                "cwd": str(checkout), "args": ["-w", "--stdout", "--no-update-check"]
            }

            run("new-window", "-n", "copy", "-c", str(checkout),
                "printf 'copy sample\\n'; /bin/sleep 120")
            wait_for(lambda: "copy sample" in run("capture-pane", "-p"))
            press(b"\x01[")
            run("send-keys", "-X", "history-top")
            run("send-keys", "-X", "start-of-line")
            press(b"v")
            run("send-keys", "-X", "end-of-line")
            press(b"y")
            assert "copy sample" in run("show-buffer")
            assert run("display-message", "-p", "#{pane_in_mode}") == "0"

            def left_label():
                return run("display-message", "-p", "-c", client_name,
                           "#{E:status-left}")

            assert "|" in left_label()
            assert "bg=#e0af68" not in left_label()
            idle_left = re.sub(r"#\[[^]]*\]", "", left_label())
            press(b"\x01")
            wait_for(lambda: run("display-message", "-p", "-c", client_name,
                                 "#{client_prefix}") == "1")
            active_style = left_label()
            assert "bg=#e0af68" in active_style.split("|", 1)[0]
            assert "bg=#e0af68" not in active_style.split("|", 1)[1]
            active_left = re.sub(r"#\[[^]]*\]", "", active_style)
            assert active_left == idle_left
            assert "CTRL+A" not in run("show-options", "-gv", "status-right")
            press(b"\x1b")
            wait_for(lambda: "bg=#e0af68" not in left_label())
            fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 70, 0, 0))
            os.kill(client.pid, signal.SIGWINCH)
            wait_for(lambda: run("list-clients", "-F", "#{client_width}") == "70")
            assert "|" not in left_label()
            press(b"\x01")
            wait_for(lambda: "bg=#e0af68" in left_label())
            assert "baseline" in left_label()
            press(b"\x1b")
            wait_for(lambda: "bg=#e0af68" not in left_label())
            right = run("display-message", "-p", "-c", client_name,
                        "#{T:status-right}")
            assert not re.search(r"\d\d:\d\d", right)
            assert "#{" not in left_label() + right

            scratch_env = dict(env, DOTFILES_TMUX_CLIENT=client_name,
                               DOTFILES_TMUX_SOCKET=str(socket))

            def scratch(name, check=True, choice="\n", **extra_env):
                result = subprocess.run(
                    [sys.executable, str(helper), name],
                    env=dict(scratch_env, **extra_env), input=choice, capture_output=True,
                    text=True, timeout=5,
                )
                if check and result.returncode:
                    raise RuntimeError(result.stderr or "Scratch helper failed")
                return result

            traces = root / "agent traces"
            traces.mkdir()
            run("set-environment", "-g", "DOTFILES_AGENT_TRACES", str(traces))

            def install_stub(tool):
                (tools / tool).write_text(
                    "#!" + sys.executable + "\n"
                    "import json, os, sys, time\n"
                    "from pathlib import Path\n"
                    "name = Path(sys.argv[0]).name\n"
                    "trace = Path(os.environ['DOTFILES_AGENT_TRACES']) / (name + '-' + str(os.getpid()) + '.json')\n"
                    "trace.write_text(json.dumps({'tool': name, 'cwd': os.getcwd(), 'args': sys.argv[1:]}))\n"
                    "sys.stdout.write('\\x1b]2;fixture agent title\\x07'); sys.stdout.flush()\n"
                    "time.sleep(120)\n"
                )
                (tools / tool).chmod(0o700)

            for tool in ("codex", "claude"):
                install_stub(tool)
            preference = fixture_home / ".local/state/dotfiles/last-agent"

            def active_pane():
                return run("display-message", "-p", "-c", client_name, "#{pane_id}")

            def active_agent():
                return run("display-message", "-p", "-c", client_name,
                           "#{@dotfiles_agent}")

            original_panes = run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}")
            # Exercise real popup dispatch using only synthetic agent executables.
            press(b"\x01N")
            press(b"\x03")
            assert not scratch_root.exists()
            assert not preference.exists()
            terminal_output.clear()
            menu_started = time.perf_counter()
            os.write(master, b"\x01N")
            wait_for(lambda: b"Agent for new launches:" in terminal_output)
            launcher_popup_ms = (time.perf_counter() - menu_started) * 1000
            press(b"jklh")  # Both action directions and both agent directions.
            press(b"\r")
            press(b"draft\x1b")  # Back from naming without creating a task.
            assert not scratch_root.exists()
            press(b"t\x15team-update\r")
            wait_for(lambda: run("list-clients", "-F", "#{session_name}") == "scratch")
            task_dir = scratch_root / "team-update"
            assert run("display-message", "-p", "-c", client_name,
                       "#{pane_current_path}") == str(task_dir)
            assert active_agent() == "codex"
            assert preference.read_text() == "codex\n"
            assert preference.stat().st_mode & 0o777 == 0o600
            assert task_dir.stat().st_mode & 0o777 == 0o700
            draft = task_dir / "draft.txt"
            draft.write_text("Keep this draft.\n")
            pane = active_pane()
            press(b"\x01b")
            assert run("list-clients", "-F", "#{session_name}") == "baseline"
            scratch_started = time.perf_counter()
            scratch("team-update")
            scratch_reopen_ms = (time.perf_counter() - scratch_started) * 1000
            assert active_pane() == pane
            assert len(run("list-windows", "-t", "=scratch").splitlines()) == 1
            assert draft.read_text() == "Keep this draft.\n"
            scratch("research", choice="2\n")
            assert active_agent() == "claude"
            assert preference.read_text() == "claude\n"
            assert len(run("list-windows", "-t", "=scratch").splitlines()) == 2
            cancelled_panes = run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}")
            scratch("cancelled", choice="")  # EOF at the agent prompt cancels.
            assert not (scratch_root / "cancelled").exists()
            assert run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}") == cancelled_panes
            assert preference.read_text() == "claude\n"
            run("kill-window", "-t", "=scratch:=team-update")
            assert draft.read_text() == "Keep this draft.\n"
            scratch("team-update")
            assert active_pane() != pane
            assert active_agent() == "claude"  # Closed task uses the remembered choice.
            assert run("display-message", "-p", "-c", client_name,
                       "#{pane_current_path}") == str(task_dir)
            assert draft.read_text() == "Keep this draft.\n"
            live_pane = active_pane()
            press(b"\x01N")
            press(b"h\rteam-update\r")  # A different launch choice preserves the live task.
            assert active_pane() == live_pane
            assert active_agent() == "claude"
            assert preference.read_text() == "claude\n"
            before_invalid = run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}")
            for name in ("../outside", "bad;name", "a" * 65):
                assert scratch(name, check=False).returncode != 0
            (scratch_root / "linked").symlink_to(checkout, target_is_directory=True)
            assert scratch("linked", check=False).returncode != 0
            blocked = root / "tracked checkout"
            blocked.mkdir()
            subprocess.run([shutil.which("git"), "init", "-q", str(blocked)],
                           env=env, capture_output=True, check=True, timeout=5)
            assert scratch("blocked", check=False,
                           DOTFILES_SCRATCH_ROOT=str(blocked / "scratch")).returncode != 0
            assert not (blocked / "scratch").exists()
            assert run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}") == before_invalid

            source_pane = active_pane()
            panes_before_agents = run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}")
            press(b"\x01N")
            press(b"jl\x1b")  # Cancel after changing both action and agent.
            assert run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}") == panes_before_agents
            assert preference.read_text() == "claude\n"
            (tools / "codex").unlink()
            press(b"\x01N")
            press(b"jh\r")
            wait_for(lambda: b"Install codex" in terminal_output)
            press(b"\x1b")
            assert run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}") == panes_before_agents
            assert preference.read_text() == "claude\n"
            install_stub("codex")

            def choose_agent(choice, name):
                old = active_pane()
                press(b"\x01N")
                press(choice + b"p")
                wait_for(lambda: active_pane() != old and active_agent() == name)
                return active_pane()

            claude_pane = choose_agent(b"", "claude")
            assert len(run("list-panes").splitlines()) == 2
            codex_pane = choose_agent(b"h", "codex")
            assert preference.read_text() == "codex\n"
            another_codex = choose_agent(b"", "codex")
            assert another_codex != codex_pane
            assert len(run("list-panes").splitlines()) == 4
            assert run("display-message", "-p", "#{window_zoomed_flag}") == "1"
            for target in (source_pane, codex_pane, claude_pane):
                assert run("display-message", "-p", "-t", target, "#{pane_dead}") == "0"
            assert draft.read_text() == "Keep this draft.\n"

            def agent(tool, source, check=True, **extra_env):
                result = subprocess.run(
                    [sys.executable, str(agent_helper)] + ([tool] if tool else []),
                    env=dict(scratch_env, DOTFILES_TMUX_PANE=source, **extra_env),
                    input="\n", capture_output=True, text=True, timeout=5,
                )
                if check and result.returncode:
                    raise RuntimeError(result.stderr or "Agent helper failed")
                return result

            before_invalid = run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}")
            assert agent("invalid", source_pane, check=False).returncode != 0
            assert agent("codex", "%99999", check=False).returncode != 0
            assert agent("codex", source_pane, check=False,
                         XDG_STATE_HOME="relative").returncode != 0
            assert run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}") == before_invalid
            assert preference.read_text() == "codex\n"

            # New sessions are separate workspaces, preserving the invoking folder.
            before_session = run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}")
            press(b"\x01N")
            press(b"sisolated-task\r")
            wait_for(lambda: run("list-clients", "-F", "#{session_name}") == "isolated-task")
            assert active_agent() == "codex"
            assert run("display-message", "-p", "-c", client_name,
                       "#{pane_current_path}") == str(task_dir)
            assert len(run("list-panes", "-s", "-t", "=isolated-task").splitlines()) == 1
            assert len(run("list-windows", "-t", "=isolated-task").splitlines()) == 1
            assert all(pane in run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}")
                       for pane in before_session.splitlines())
            assert preference.read_text() == "codex\n"
            press(b"\x01b")
            assert run("list-clients", "-F", "#{session_name}") == "scratch"
            unchanged = run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}")
            press(b"\x01N")
            press(b"sunfinished\x1b\x1b")
            assert run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}") == unchanged
            assert "unfinished" not in run("list-sessions", "-F", "#{session_name}").splitlines()
            for name, error in (("isolated-task", b"already exists"),
                                ("bad:name", b"session name"),
                                ("scratch", b"reserved")):
                terminal_output.clear()
                press(b"\x01N")
                press(b"jj\r" + name.encode() + b"\r")
                wait_for(lambda: error in terminal_output)
                press(b"\x1b")
                assert run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}") == unchanged
                assert preference.read_text() == "codex\n"
            # Restore the fixture's previous-session order after checking Ctrl+A, b.
            run("switch-client", "-c", client_name, "-t", "=baseline")
            run("switch-client", "-c", client_name, "-t", "=scratch")

            # A new project pane shares the default; all launches are new conversations.
            run("new-window", "-n", "project", "-c", str(checkout))
            project_source = active_pane()
            agent_started = time.perf_counter()
            agent(None, project_source)
            agent_launch_ms = (time.perf_counter() - agent_started) * 1000
            project_agent = active_pane()
            assert active_agent() == "codex"
            assert run("display-message", "-p", "#{pane_current_path}") == str(checkout)
            agent("claude", project_agent)
            assert preference.read_text() == "claude\n"
            # Popup action shortcuts use the selected/default agent, including switches.
            before_fast = run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}")
            for tool in ("codex", "claude"):
                old = active_pane()
                press(b"\x01N")
                press(b"hp")
                wait_for(lambda: active_pane() != old and active_agent() == tool)
                assert run("display-message", "-p", "-c", client_name,
                           "#{pane_current_path}") == str(checkout)
                assert preference.read_text() == tool + "\n"
                assert run("display-message", "-p", "#{window_zoomed_flag}") == "1"
            assert all(pane in run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}")
                       for pane in before_fast.splitlines())
            # Named panes get stable captions, without affecting ordinary windows.
            assert run("show-options", "-wAv", "-t", project_source,
                       "pane-border-status") == "off"
            run("new-window", "-n", "named-pane", "-c", str(checkout))
            named_source = active_pane()
            before_named = run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}")
            press(b"\x01N")
            press(b"Punfinished\x1b\x1b")
            assert run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}") == before_named
            press(b"\x01N")
            press(b"P\r")  # Blank names cancel without starting another agent.
            assert run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}") == before_named
            terminal_output.clear()
            press(b"\x01N")
            press(b"Pbad#label\r")
            wait_for(lambda: b"pane name" in terminal_output)
            press(b"\x1b")
            assert run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}") == before_named
            assert run("show-options", "-wAv", "-t", named_source,
                       "pane-border-status") == "off"
            assert preference.read_text() == "claude\n"
            label = "API Review: v2"
            press(b"\x01N")
            press(b"P" + label.encode())
            named_started = time.perf_counter()
            os.write(master, b"\r")
            wait_for(lambda: active_pane() != named_source
                     and active_agent() == "claude"
                     and run("display-message", "-p", "-c", client_name, "#{pane_dead}") == "0")
            named_pane_ready_ms = (time.perf_counter() - named_started) * 1000
            named_pane = active_pane()
            named_window = run("display-message", "-p", "-t", named_pane, "#{window_id}")
            assert run("display-message", "-p", "-t", named_pane,
                       "#{@dotfiles_pane_name}") == label
            wait_for(lambda: run("display-message", "-p", "-t", named_pane,
                                 "#{pane_title}") == "fixture agent title")
            assert run("show-options", "-wAv", "-t", named_pane,
                       "pane-border-status") == "top"
            border = run("show-options", "-gwv", "pane-border-format")
            caption = run("display-message", "-p", "-t", named_pane, border)
            assert label in caption and "(claude)" in caption and "#{" not in caption
            terminal_output.clear()
            run("refresh-client", "-t", client_name)
            wait_for(lambda: label.encode() in terminal_output)
            press(b"\x01z")
            assert run("display-message", "-p", "#{window_zoomed_flag}") == "0"
            assert run("display-message", "-p", "-t", named_source, "#{pane_dead}") == "0"
            assert all(pane in run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}")
                       for pane in before_named.splitlines())
            run("source-file", str(config))
            assert run("display-message", "-p", "-t", named_pane,
                       "#{@dotfiles_pane_name}") == label
            assert run("show-options", "-wAv", "-t", named_pane,
                       "pane-border-status") == "top"
            assert run("show-options", "-wAv", "-t", project_source,
                       "pane-border-status") == "off"
            # Real fzf shares the popup TTY; cancel/back never launches or records a folder.
            recent = fixture_home / ".local/state/dotfiles/recent-folders.json"
            picker_before = run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}")
            recent_before = recent.read_bytes()
            terminal_output.clear()
            press(b"\x01N")
            picker_started = time.perf_counter()
            os.write(master, b"f")
            wait_for(lambda: b"Enter choose" in terminal_output)
            folder_picker_ready_ms = (time.perf_counter() - picker_started) * 1000
            press(b"\x1b")
            wait_for(lambda: b"Open workspace" in terminal_output)
            press(b"\x1b")
            assert run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}") == picker_before
            assert recent.read_bytes() == recent_before
            assert preference.read_text() == "claude\n"
            # Personal fzf options cannot add commands or break this picker.
            run("set-environment", "-g", "FZF_DEFAULT_OPTS", "--this-option-does-not-exist")
            run("set-environment", "-g", "FZF_DEFAULT_OPTS_FILE", "/missing-fzfrc")

            def open_picker(shortcut=b"f"):
                terminal_output.clear()
                press(b"\x01N")
                press(shortcut)
                wait_for(lambda: b"Enter choose" in terminal_output)

            def choose_folder(query, name):
                press(query.encode())
                terminal_output.clear()
                press(b"\r")
                wait_for(lambda: ("Name: " + name).encode() in terminal_output)

            open_picker()
            choose_folder("Alpha Project", "alpha-project")
            press(b"\x03")
            assert recent.read_bytes() == recent_before
            assert run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}") == picker_before
            open_picker()
            choose_folder("Alpha Project", "alpha-project")
            press(b"\r")
            wait_for(lambda: run("list-clients", "-F", "#{session_name}") == "alpha-project")
            assert active_agent() == "claude"
            assert run("display-message", "-p", "-c", client_name, "#{pane_current_path}") == str(alpha)
            assert json.loads(recent.read_text())[0] == str(alpha)
            assert recent.stat().st_mode & 0o777 == 0o600
            assert all(pane in run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}")
                       for pane in picker_before.splitlines())
            press(b"\x01b")
            assert run("list-clients", "-F", "#{session_name}") == "scratch"
            open_picker(b"spicked-review\x06")  # Ctrl+F while naming preserves the name.
            choose_folder("Beta Project", "picked-review")
            press(b"\r")
            wait_for(lambda: run("list-clients", "-F", "#{session_name}") == "picked-review")
            assert run("display-message", "-p", "-c", client_name, "#{pane_current_path}") == str(beta)
            assert json.loads(recent.read_text())[:2] == [str(beta), str(alpha)]
            press(b"\x01b")
            unchanged_picker = run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}")
            latest_recent = recent.read_bytes()
            open_picker(b"sdraft-name\x06")
            press(b"\x1b")
            wait_for(lambda: b"Name: draft-name" in terminal_output)
            press(b"\x03")
            assert recent.read_bytes() == latest_recent
            # Native fzf query output supports shell-style paths without shell evaluation.
            for path, name in (("~", "home-pilot"), ("~/Documents/My Folder", "my-folder"),
                               (str(home_folder), "my-folder"), (str(literal_tilde), "literal-folder"),
                               (str(outside), "outside"), ("./src/internal", "internal"),
                               ("../outside", "outside")):
                # Relative paths resolve against the invoking pane's folder.
                if path.startswith("."):
                    run("switch-client", "-c", client_name, "-t", "=alpha-project" if path.startswith("./") else "=baseline")
                drain(0.15)  # Let the synthetic client finish a session switch before typing.
                open_picker()
                choose_folder(path, name)
                assert run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}") == unchanged_picker
                press(b"\x03")
                assert recent.read_bytes() == latest_recent
                run("switch-client", "-c", client_name, "-t", "=scratch")
                drain(0.15)
            # Absolute and ~/ prefixes must match home folders as well as paths outside home.
            for prefix in (str(home_project)[:-3], str(home_project).lower()[:-3],
                           "~/workspace/Absolute Proj"):
                open_picker()
                terminal_output.clear()
                press(prefix.encode())
                terminal_output.clear()
                press(b"\r")
                wait_for(lambda: b"Name: absolute-project" in terminal_output)
                press(b"\x03")
                assert recent.read_bytes() == latest_recent
                assert run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}") == unchanged_picker
            # Bracketed-paste does not run the ~ key binding; literal path expansion still works.
            open_picker()
            press(b"\x1b[200~~/Documents/My Folder\x1b[201~")
            terminal_output.clear()
            press(b"\r")
            wait_for(lambda: b"Name: my-folder" in terminal_output)
            press(b"\x03")
            # Tab browses only the requested level; hidden folders remain accessible.
            open_picker()
            press(b"~\t")
            wait_for(lambda: b".hidden-folder" in terminal_output)
            press(b"Documents\t")
            wait_for(lambda: b"My Folder" in terminal_output)
            terminal_output.clear()
            press(b"My Folder\r")
            wait_for(lambda: b"Name: my-folder" in terminal_output)
            press(b"\x03")
            open_picker()
            press(b"~/Documents\t")
            terminal_output.clear()
            press(b"\x1bh")  # Alt+h goes back to the browsed directory's parent.
            wait_for(lambda: b".hidden-folder" in terminal_output)
            press(b"\x1b")
            press(b"\x03")
            # An invalid typed path stays in the picker and can be corrected.
            open_picker()
            press(b"~/does-not-exist\r")
            wait_for(lambda: b"Folder not found" in terminal_output)
            press(b"\x15~/Documents/My Folder")
            terminal_output.clear()
            press(b"\r")
            wait_for(lambda: b"Name: my-folder" in terminal_output)
            press(b"\r")
            wait_for(lambda: run("list-clients", "-F", "#{session_name}") == "my-folder")
            assert run("display-message", "-p", "-c", client_name, "#{pane_current_path}") == str(home_folder)
            assert json.loads(recent.read_text())[0] == str(home_folder)
            press(b"\x01b")
            unchanged_picker = run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}")
            latest_recent = recent.read_bytes()
            # Missing dependencies or invalid roots remain visible without creating sessions.
            (tools / "fzf").unlink()
            terminal_output.clear()
            press(b"\x01N")
            press(b"f")
            wait_for(lambda: b"Install fzf separately" in terminal_output)
            press(b"\x1b")
            (tools / "fzf").symlink_to(fzf)
            run("set-environment", "-g", "DOTFILES_PROJECT_ROOTS", "relative")
            terminal_output.clear()
            press(b"\x01N")
            press(b"f")
            wait_for(lambda: b"absolute paths" in terminal_output)
            press(b"\x1b")
            run("set-environment", "-g", "DOTFILES_PROJECT_ROOTS", env["DOTFILES_PROJECT_ROOTS"])
            assert run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}") == unchanged_picker
            assert recent.read_bytes() == latest_recent
            assert preference.read_text() == "claude\n"
            # Deleted folders are filtered from recents before the next search.
            deleted = root / "deleted-folder"
            deleted.mkdir()
            with patch.dict(os.environ, env, clear=True):
                launcher["remember_folder"](str(deleted))
                deleted.rmdir()
                assert deleted not in launcher["recent_folders"]()
                assert str(beta) in launcher["folder_candidates"](str(checkout))
                assert launcher["folder_label"](str(home_folder)) == "~/Documents/My Folder"
            run("set-environment", "-gu", "FZF_DEFAULT_OPTS")
            run("set-environment", "-gu", "FZF_DEFAULT_OPTS_FILE")
            scratch("shared-default")
            assert active_agent() == "claude"
            shared_dir = scratch_root / "shared-default"
            wait_for(lambda: any(json.loads(p.read_text())["cwd"] == str(shared_dir)
                                 for p in traces.glob("claude-*.json")))
            for trace in traces.glob("*.json"):
                assert json.loads(trace.read_text())["args"] == []

            # Fast startup failures retain a dead pane without replacing the source.
            (tools / "claude").write_text("#!/bin/sh\nprintf 'fixture startup failure\\n'\nexit 1\n")
            (tools / "claude").chmod(0o700)
            shared_source = active_pane()
            agent("claude", shared_source)
            failed_pane = active_pane()
            wait_for(lambda: run("display-message", "-p", "-t", failed_pane,
                                 "#{pane_dead}") == "1")
            # On tmux 3.4, fast exits sometimes retain the pane before recording
            # a status. Verify the user-visible failure and retention directly.
            assert run("display-message", "-p", "-t", failed_pane,
                       "#{pane_dead_status}") in ("", "1")
            assert "fixture startup failure" in run("capture-pane", "-p", "-J", "-S", "-100", "-t", failed_pane)
            assert run("display-message", "-p", "-t", shared_source, "#{pane_dead}") == "0"
            press(b"\x01N")
            press(b"jj\rfailed-session\r")
            wait_for(lambda: run("list-clients", "-F", "#{session_name}") == "failed-session")
            wait_for(lambda: run("display-message", "-p", "-c", client_name,
                                 "#{pane_dead}") == "1")
            assert run("display-message", "-p", "-c", client_name,
                       "#{pane_dead_status}") in ("", "1")
            assert "fixture startup failure" in run("capture-pane", "-p", "-J", "-S", "-100", "-t", active_pane())
            press(b"\x01b")
            assert run("list-clients", "-F", "#{session_name}") == "scratch"
            run("switch-client", "-c", client_name, "-t", "=baseline")
            run("switch-client", "-c", client_name, "-t", "=scratch")
            assert all(pane in run("list-panes", "-a", "-F", "#{pane_id}:#{pane_pid}")
                       for pane in original_panes.splitlines())
            press(b"\x01b")
            assert run("list-clients", "-F", "#{session_name}") == "baseline"
            run("source-file", str(config))
            assert run("list-keys", "-T", "prefix") == bindings

            report = {"tmux": run("-V"), "checks": "passed",
                      "private_server_start_ms": round(startup_ms, 1),
                      "scratch_reopen_ms": round(scratch_reopen_ms, 1),
                      "agent_launch_ms": round(agent_launch_ms, 1),
                      "launcher_popup_ready_ms": round(launcher_popup_ms, 1),
                      "named_pane_ready_ms": round(named_pane_ready_ms, 1),
                      "folder_candidates_ms": round(folder_candidates_ms, 1),
                      "folder_picker_ready_ms": round(folder_picker_ready_ms, 1),
                      "ssh_clipboard": "actual client verification pending"}
            if sys.platform.startswith("linux"):
                # Measure idle redraw overhead with native named-pane captions visible.
                run("select-window", "-t", named_window)
                run("switch-client", "-c", client_name, "-t", "=scratch")
                pid = int(run("display-message", "-p", "#{pid}"))
                stat_file = Path(f"/proc/{pid}/stat")
                def ticks():
                    fields = stat_file.read_text().rsplit(")", 1)[1].split()
                    return int(fields[11]) + int(fields[12])
                before = ticks()
                sample_started = time.monotonic()
                drain(2)
                elapsed = time.monotonic() - sample_started
                report["idle_cpu_percent_sample"] = round(
                    (ticks() - before) / os.sysconf("SC_CLK_TCK") / elapsed * 100, 2
                )
            print(json.dumps(report, indent=2))
        finally:
            subprocess.run(command + ["kill-server"], env=env, capture_output=True,
                           timeout=5)
            if client is not None:
                try:
                    client.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    client.terminate()
                    client.wait(timeout=2)
            if master is not None:
                os.close(master)


if __name__ == "__main__":
    main()
