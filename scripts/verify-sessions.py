#!/usr/bin/env python3
"""Check owned session-picker behavior and pane moves on a disposable tmux server.

Uses synthetic sleeping panes, two PTY clients and isolated private preferences.
Never attaches to the user's server, launches an agent, or reads the clipboard.
"""

from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
import os
from pathlib import Path
import pty
import re
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
    tmux = shutil.which("tmux")
    if not tmux:
        raise SystemExit("tmux is required")
    repo = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, str(repo / "scripts/sync-tmux-keys.py"), "--check"], check=True)
    with tempfile.TemporaryDirectory(prefix="dotfiles-sessions-") as temporary:
        root = Path(temporary)
        home = root / "home ' quoted"
        tools = home / ".local/bin"
        tools.mkdir(parents=True)
        shutil.copyfile(repo / "home/dot_local/bin/executable_tmux-sessions", tools / "tmux-sessions")
        (tools / "tmux-sessions").chmod(0o700)
        shutil.copyfile(repo / "home/dot_local/bin/tmux_keys.py", tools / "tmux_keys.py")
        env = {key: value for key, value in os.environ.items()
               if key not in ("TMUX", "TMUX_PANE", "BASH_ENV", "ENV")}
        env.update(HOME=str(home), XDG_STATE_HOME=str(home / ".local/state"), TERM="xterm-256color")
        socket = root / "server.sock"
        env["DOTFILES_TMUX_SOCKET"] = str(socket)
        command = [tmux, "-S", str(socket)]
        clients, masters, output = [], [], bytearray()

        def run(*args):
            result = subprocess.run(command + list(args), env=env, text=True,
                                    capture_output=True, timeout=5)
            if result.returncode:
                raise RuntimeError(result.stderr or "tmux failed")
            return result.stdout.rstrip("\n")

        def drain(duration=0.03):
            deadline = time.monotonic() + duration
            while masters and time.monotonic() < deadline:
                readable = select.select(masters, [], [], 0.01)[0]
                for descriptor in readable:
                    try:
                        data = os.read(descriptor, 65536)
                        if descriptor == masters[0]:
                            output.extend(data)
                            del output[:-20000]
                    except OSError:
                        pass

        def wait_for(predicate):
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if predicate():
                    return
                drain()
            raise AssertionError("Timed out; terminal tail: " + repr(bytes(output[-1600:])))

        def press(keys):
            os.write(masters[0], keys)
            drain(0.05)

        def clean_output():
            # Captured words can be interrupted by cursor/color control sequences.
            return re.sub(rb"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))", b"", bytes(output))

        def context(client_name):
            for line in run("list-clients", "-F", "#{client_name}\t#{session_id}\t#{pane_id}").splitlines():
                name, session, pane = line.split("\t")
                if name == client_name:
                    return session, pane
            raise AssertionError("Client disappeared")

        def attach(session):
            master, slave = pty.openpty()
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
            process = subprocess.Popen(command + ["attach-session", "-t", session], env=env,
                                       stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
            os.close(slave)
            clients.append(process)
            masters.append(master)
            wait_for(lambda: len(run("list-clients", "-F", "#{client_name}").splitlines()) == len(clients))
            return next(line.split("\t")[0] for line in run("list-clients", "-F",
                        "#{client_name}\t#{client_pid}").splitlines() if line.split("\t")[1] == str(process.pid))

        def open_picker():
            drain(0.05)
            output.clear()
            started = time.perf_counter()
            os.write(masters[0], b"\x01s")
            wait_for(lambda: b"e edit key" in clean_output())
            return (time.perf_counter() - started) * 1000

        def read_state():
            return json.loads(preferences.read_text())

        def snapshot():
            return sorted(run("list-panes", "-a", "-F",
                          "#{pane_id}:#{pane_pid}:#{@dotfiles_pane_name}:#{@dotfiles_attention_notice}").splitlines())

        try:
            run("-f", str(repo / "home/dot_tmux.conf"), "new-session", "-d", "-s", "source",
                "-x", "120", "-y", "40", "/bin/sleep 180")
            run("set-option", "-g", "default-shell", "/bin/sh")
            source_id = run("display-message", "-p", "#{session_id}")
            source_pane = run("display-message", "-p", "#{pane_id}")
            for name in ("dev", "docs", "observer", "agent # [odd] ' $(x)"):
                run("new-session", "-d", "-s", name, "/bin/sleep 180")
            actor = attach("=source")
            observer = attach("=observer")
            observer_before = context(observer)
            original = snapshot()
            preferences = home / ".local/state/dotfiles/sessions/preferences.json"
            with patch.dict(os.environ, env, clear=True):
                helper = runpy.run_path(str(tools / "tmux-sessions"))
                started = time.perf_counter()
                rows = helper["session_rows"](run)
                first_ms = (time.perf_counter() - started) * 1000
                original_keys = {row["name"]: row["key"] for row in rows}
                assert len(set(original_keys.values())) == len(rows)
                assert all(key.isalpha() and key not in "ejkqJK" for key in original_keys.values())
                assert preferences.stat().st_mode & 0o777 == 0o600
                assert preferences.parent.stat().st_mode & 0o777 == 0o700

                # Saved names survive a new native ID; closed sessions don't block reorders.
                run("new-session", "-d", "-s", "reopened", "/bin/sleep 180")
                before = next(row for row in helper["session_rows"](run) if row["name"] == "reopened")
                run("kill-session", "-t", before["id"])
                run("new-session", "-d", "-s", "reopened", "/bin/sleep 180")
                after = next(row for row in helper["session_rows"](run) if row["name"] == "reopened")
                assert before["id"] != after["id"] and before["key"] == after["key"]
                run("kill-session", "-t", after["id"])
                rows = helper["session_rows"](run, "refresh", "reopened")
                assert not any(row["name"] == "reopened" for row in rows)

                # New picker controls migrate only conflicting saved shortcuts,
                # including closed names; keep order, explicit blanks and others.
                saved_state = read_state()
                legacy = json.loads(json.dumps(saved_state))
                legacy["keys"].update(dev="e", docs="J", reopened="K", source="")
                preferences.write_text(json.dumps(legacy))
                migrated = helper["session_rows"](run)
                migrated_state = read_state()
                assert migrated_state["order"] == legacy["order"]
                assert migrated_state["keys"]["source"] == ""
                assert all(key not in "ejkqJK" for key in migrated_state["keys"].values() if key)
                assert all(migrated_state["keys"][name] == key for name, key in legacy["keys"].items()
                           if name not in ("dev", "docs", "reopened"))
                assert len(set(key for key in migrated_state["keys"].values() if key)) == len(
                    [key for key in migrated_state["keys"].values() if key])
                assert helper["session_rows"](run) == migrated  # Repeat migration is stable.
                preferences.write_text(json.dumps(saved_state))

                # Locking merges concurrent edits from separate picker snapshots.
                with ThreadPoolExecutor(max_workers=2) as pool:
                    futures = [pool.submit(helper["session_rows"], run, "key", name, key)
                               for name, key in (("dev", "D"), ("docs", "M"))]
                    for future in futures:
                        future.result()
                assert read_state()["keys"]["dev"] == "D" and read_state()["keys"]["docs"] == "M"

                # Reject malformed state without overwriting it or following symlinks.
                saved = preferences.read_bytes()
                preferences.write_text('{"version":1,"order":[],"keys":{"bad":"ab"}}')
                try:
                    helper["session_rows"](run)
                    raise AssertionError("Malformed shortcut accepted")
                except ValueError:
                    pass
                assert preferences.read_text().endswith('"ab"}}')
                preferences.write_bytes(saved)
                external = root / "external-private.json"
                external.write_bytes(saved)
                preferences.unlink()
                preferences.symlink_to(external)
                try:
                    helper["session_rows"](run)
                    raise AssertionError("Preference symlink accepted")
                except ValueError:
                    pass
                assert external.read_bytes() == saved
                preferences.unlink()
                preferences.write_bytes(saved)
                preferences.chmod(0o600)

                popup_ms = open_picker()
                initial_order = read_state()["order"][:]
                press(b"K")
                wait_for(lambda: read_state()["order"] != initial_order)
                changed = read_state()["order"][:]
                assert changed.index("source") < initial_order.index("source")
                press(b"J")
                wait_for(lambda: read_state()["order"] == initial_order)
                press(b"eX")
                wait_for(lambda: read_state()["keys"]["source"] == "X")
                press(b"eD")
                wait_for(lambda: b"belongs to dev" in clean_output())
                assert read_state()["keys"]["source"] == "X"
                press(b"eJ")
                wait_for(lambda: b"are reserved" in clean_output())
                assert read_state()["keys"]["source"] == "X" and read_state()["order"] == initial_order
                press(b"e\x1b")
                press(b"q")
                assert context(actor) == (source_id, source_pane)
                assert context(observer) == observer_before

                # Direct letter jumps close the popup before switching this client.
                open_picker()
                press(b"D")
                dev_id = next(row["id"] for row in helper["session_rows"](run) if row["name"] == "dev")
                wait_for(lambda: context(actor)[0] == dev_id)
                assert context(observer) == observer_before
                open_picker()
                press(b"X")
                wait_for(lambda: context(actor) == (source_id, source_pane))

                # Vim navigation + Enter opens exactly the highlighted row.
                open_picker()
                live_order = helper["session_rows"](run)
                source_index = next(i for i, row in enumerate(live_order) if row["id"] == source_id)
                previous_id = live_order[source_index - 1]["id"]
                press(b"k\r")
                wait_for(lambda: context(actor)[0] == previous_id)
                assert context(observer) == observer_before
                open_picker()
                press(b"j\r")
                wait_for(lambda: context(actor) == (source_id, source_pane))

                # Clearing and cancellation remain distinct; refreshed/new rows retain keys.
                open_picker()
                press(b"e\x7f")
                wait_for(lambda: read_state()["keys"]["source"] == "")
                press(b"\x0c")
                press(b"eX")
                wait_for(lambda: read_state()["keys"]["source"] == "X")
                press(b"\x1b")
                assert snapshot() == original

                # A narrow terminal still accepts real shifted keys and letter jumps.
                fcntl.ioctl(masters[0], termios.TIOCSWINSZ, struct.pack("HHHH", 24, 70, 0, 0))
                import signal
                os.kill(clients[0].pid, signal.SIGWINCH)
                drain(0.15)
                narrow_ms = open_picker()
                press(b"\x1b[1;2A")
                wait_for(lambda: read_state()["order"] != initial_order)
                press(b"\x1b[1;2B")
                wait_for(lambda: read_state()["order"] == initial_order)
                press(b"K")
                wait_for(lambda: read_state()["order"] != initial_order)
                press(b"J")
                wait_for(lambda: read_state()["order"] == initial_order)
                run("new-session", "-d", "-s", "late", "/bin/sleep 180")
                assert "late" not in read_state()["keys"]
                press(b"\x0c")
                wait_for(lambda: "late" in read_state()["keys"])
                run("kill-session", "-t", "=late")
                press(b"\x0c")

                # Idle samples include server, clients and this blocking picker.
                server_pid = int(run("display-message", "-p", "#{pid}"))
                processes = subprocess.check_output(["ps", "-eo", "pid=,args="], text=True)
                picker_pids = [int(line.strip().split(None, 1)[0]) for line in processes.splitlines()
                               if str(tools / "tmux-sessions") in line and "python" in line]
                sample_pids = [server_pid] + [client.pid for client in clients] + picker_pids

                def ticks(pid):
                    values = Path('/proc/' + str(pid) + '/stat').read_text().rpartition(') ')[2].split()
                    return int(values[11]) + int(values[12])

                idle_before = sum(ticks(pid) for pid in sample_pids)
                time.sleep(1)
                idle_ticks = sum(ticks(pid) for pid in sample_pids) - idle_before
                idle_cpu = idle_ticks / os.sysconf('SC_CLK_TCK') * 100
                press(b"q")

            # Spatial pane swaps preserve IDs/PIDs/private labels and ignore marked panes.
            right = run("split-window", "-h", "-d", "-t", source_pane, "-P", "-F", "#{pane_id}", "/bin/sleep 180")
            run("split-window", "-v", "-d", "-t", source_pane, "/bin/sleep 180")
            run("split-window", "-v", "-d", "-t", right, "/bin/sleep 180")
            run("set-option", "-p", "-t", source_pane, "@dotfiles_pane_name", "kept-name")
            run("set-option", "-p", "-t", source_pane, "@dotfiles_attention_notice", "kept-notice")
            run("set-option", "-p", "-t", source_pane, "@dotfiles_agent_record", "kept-record")
            run("select-pane", "-m", "-t", "=observer:")
            run("select-pane", "-t", source_pane)
            pane_snapshot = snapshot()

            def position():
                return run("display-message", "-p", "-t", source_pane, "#{pane_left}:#{pane_top}")

            # In a 2x2 layout, right/down/left/up returns to the original cell.
            original_position = position()
            for arrow in (b"C", b"B", b"D", b"A"):
                before = position()
                press(b"\x01\x1b[1;2" + arrow)
                wait_for(lambda: position() != before)
                assert context(actor)[1] == source_pane
                assert context(observer) == observer_before
                assert snapshot() == pane_snapshot
                assert run("show-option", "-pqv", "-t", source_pane, "@dotfiles_agent_record") == "kept-record"
            assert position() == original_position
            press(b"\x01\x1b[1;2A")  # Already at the top: no wrap.
            assert position() == original_position
            run("resize-pane", "-Z", "-t", source_pane)
            press(b"\x01\x1b[1;2C")
            wait_for(lambda: position() != original_position)
            assert run("display-message", "-p", "-t", source_pane, "#{window_zoomed_flag}") == "0"
            assert context(actor)[1] == source_pane and snapshot() == pane_snapshot
            print("Passed: stable/private keys, assignment/clear/cancel, concurrent writes, malformed state,")
            print("reserved-key migration, e editing, J/K and Shift-arrow ordering, reopened names, letter jumps,")
            print("two-client routing, 120/70-column UI,")
            print("pane swaps/focus/edges/zoom/marked-pane safety and preserved processes/metadata.")
            print("First inventory {:.1f} ms; popup {:.1f}/{:.1f} ms; one-second idle CPU {:.1f}%.".format(
                  first_ms, popup_ms, narrow_ms, idle_cpu))
        finally:
            subprocess.run(command + ["kill-server"], env=env, capture_output=True)
            for client in clients:
                try:
                    client.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    client.terminate()
                    client.wait(timeout=3)
            for master in masters:
                os.close(master)


if __name__ == "__main__":
    main()
