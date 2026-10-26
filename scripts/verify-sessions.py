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
import signal
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

        def mouse(x, y, button=0, release=True, client_index=0):
            # Real SGR terminal input, with zero-based screen coordinates here.
            packet = "\x1b[<{};{};{}M".format(button, x + 1, y + 1)
            if release and button < 64:
                packet += "\x1b[<{};{};{}m".format(button, x + 1, y + 1)
            os.write(masters[client_index], packet.encode())
            drain(0.05)

        def client_details(client_name):
            for line in run("list-clients", "-F",
                            "#{client_name}\t#{session_name}\t#{client_width}\t#{client_height}").splitlines():
                name, session, width, height = line.split("\t")
                if name == client_name:
                    return session, int(width), int(height)
            raise AssertionError("Client disappeared")

        def status_text(client_name, side):
            # Freeze the pane too: display-message -c alone can use another session.
            styled = run("display-message", "-p", "-c", client_name, "-t", context(client_name)[1],
                         "#{T:status-" + side + "}")
            return re.sub(r"#\[[^]]*\]", "", styled)

        def click_session_name():
            name, _, height = client_details(actor)
            left = status_text(actor, "left")
            assert name in left, left
            mouse(left.index(name) + len(name) // 2, height - 1)

        def click_last(client_name, client_index=0):
            _, width, height = client_details(client_name)
            right = status_text(client_name, "right")
            mouse(width - len(right) + right.index("[Last]") + 2, height - 1,
                  client_index=client_index)

        def popup_cell(row):
            _, width, height = client_details(actor)
            popup_width, popup_height = width * 80 // 100, height * 75 // 100
            return ((width - popup_width - 1) // 2 + 2,
                    (height - popup_height - 1) // 2 + 1 + row)

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

        def open_picker(by_mouse=False):
            drain(0.05)
            output.clear()
            started = time.perf_counter()
            if by_mouse:
                click_session_name()
            else:
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
                for previous_session in (source_id, dev_id):
                    press(b"\x01o")
                    wait_for(lambda: context(actor)[0] == previous_session)
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

                # Status-name clicks open the same picker on just the invoking
                # client. Header/drag/edit events must never switch sessions.
                mouse_readiness = []
                for width, height in ((120, 40), (70, 24)):
                    fcntl.ioctl(masters[0], termios.TIOCSWINSZ, struct.pack("HHHH", height, width, 0, 0))
                    os.kill(clients[0].pid, signal.SIGWINCH)
                    wait_for(lambda: client_details(actor)[1:] == (width, height))
                    mouse_readiness.append(open_picker(by_mouse=True))
                    visible = helper["session_rows"](run)
                    dev_index = next(i for i, row in enumerate(visible) if row["id"] == dev_id)
                    docs_index = next(i for i, row in enumerate(visible) if row["name"] == "docs")
                    mouse(*popup_cell(0))  # Header is inert.
                    press(b"e")
                    saved = preferences.read_bytes()
                    mouse(*popup_cell(3 + dev_index))
                    mouse(*popup_cell(3), button=65, release=False)
                    assert preferences.read_bytes() == saved and context(actor)[0] == source_id
                    press(b"\x1b")  # Cancel editing only.
                    x, y = popup_cell(3 + dev_index)
                    mouse(x, y, release=False)
                    x, y = popup_cell(3 + docs_index)
                    os.write(masters[0], "\x1b[<0;{};{}m".format(x + 1, y + 1).encode())
                    drain(0.05)
                    assert context(actor)[0] == source_id
                    mouse(*popup_cell(3 + dev_index))
                    wait_for(lambda: context(actor)[0] == dev_id)
                    assert context(observer) == observer_before
                    for expected_session in (source_id, dev_id, source_id):
                        click_last(actor)
                        wait_for(lambda: context(actor)[0] == expected_session)
                        assert context(observer) == observer_before

                    # Mouse-wheel selection is shared with keyboard acceptance.
                    open_picker(by_mouse=True)
                    source_index = next(i for i, row in enumerate(visible) if row["id"] == source_id)
                    mouse(*popup_cell(3), button=64, release=False)
                    press(b"\r")
                    wait_for(lambda: context(actor)[0] == visible[max(0, source_index - 1)]["id"])
                    click_last(actor)
                    wait_for(lambda: context(actor)[0] == source_id)

                    # More rows than the viewport: wheel to the end, then click
                    # the first visible row. Hit testing must include scroll offset.
                    saved = preferences.read_bytes()
                    extras = ["scroll-{:02d}".format(i) for i in range(22)]
                    try:
                        for name in extras:
                            run("new-session", "-d", "-s", name, "/bin/sleep 180")
                        open_picker(by_mouse=True)
                        visible = helper["session_rows"](run)
                        capacity = max(1, height * 75 // 100 - 9)
                        for _ in visible:
                            mouse(*popup_cell(3), button=65, release=False)
                        first_visible = visible[max(0, len(visible) - capacity)]
                        mouse(*popup_cell(3))
                        wait_for(lambda: context(actor)[0] == first_visible["id"])
                        assert context(observer) == observer_before
                        click_last(actor)
                        wait_for(lambda: context(actor)[0] == source_id)
                    finally:
                        for name in extras:
                            run("kill-session", "-t", "=" + name)
                        preferences.write_bytes(saved)

                # No previous session: the observer's Last button stays inert.
                click_last(observer, 1)
                assert context(observer) == observer_before and context(actor)[0] == source_id

                # Ordinary window-label clicks still work alongside user ranges.
                fcntl.ioctl(masters[0], termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
                os.kill(clients[0].pid, signal.SIGWINCH)
                wait_for(lambda: client_details(actor)[1:] == (120, 40))
                output.clear()
                source_window = run("display-message", "-p", "-t", source_pane, "#{window_id}")
                mouse_window = run("new-window", "-d", "-t", source_id + ":", "-n", "mouse-window",
                                   "-P", "-F", "#{window_id}", "/bin/sleep 180")
                wait_for(lambda: b"mouse-window" in clean_output())
                x = len(status_text(actor, "left"))
                separator = run("show-options", "-gwv", "window-status-separator")
                for line in run("list-windows", "-t", source_id, "-F",
                                "#{window_id}\t#{E:window-status-format}").splitlines():
                    window, text = line.split("\t", 1)
                    label = re.sub(r"#\[[^]]*\]", "", text)
                    if window == mouse_window:
                        x += label.index("mouse-window") + 2
                        break
                    x += len(label) + len(separator)
                # Tmux 3.4 combines rapid presses across different coordinates.
                # Let its 300 ms multi-click timer expire for this ordinary click;
                # rapid clicks on our release-based controls are checked above.
                drain(0.35)
                mouse(x, 39)
                wait_for(lambda: context(actor)[1] != source_pane)
                run("select-window", "-t", source_window)
                run("kill-window", "-t", mouse_window)
                assert context(observer) == observer_before and snapshot() == original

            # Spatial pane swaps preserve IDs/PIDs/private labels and ignore marked panes.
            right = run("split-window", "-h", "-d", "-t", source_pane, "-P", "-F", "#{pane_id}", "/bin/sleep 180")
            run("split-window", "-v", "-d", "-t", source_pane, "/bin/sleep 180")
            run("split-window", "-v", "-d", "-t", right, "/bin/sleep 180")
            run("set-option", "-p", "-t", source_pane, "@dotfiles_pane_name", "kept-name")
            run("set-option", "-p", "-t", source_pane, "@dotfiles_attention_notice", "kept-notice")
            run("set-option", "-p", "-t", source_pane, "@dotfiles_agent_record", "kept-record")
            run("select-pane", "-m", "-t", "=observer:")
            run("select-pane", "-t", right)
            run("select-pane", "-t", source_pane)
            pane_snapshot = snapshot()

            # Maximize/restore and spatial focus keep the underlying layout intact.
            layout_before = run("display-message", "-p", "-t", source_pane, "#{window_layout}")
            for zoomed in (False, True):
                if zoomed:
                    press(b"\x01z")
                    assert run("display-message", "-p", "-t", source_pane, "#{window_zoomed_flag}") == "1"
                for key in (b"l", b"j", b"h", b"k"):
                    press(b"\x01" + key)
                    assert run("display-message", "-p", "-t", source_pane, "#{window_zoomed_flag}") == str(int(zoomed))
                    assert context(observer) == observer_before and snapshot() == pane_snapshot
                assert context(actor)[1] == source_pane
                if zoomed:
                    press(b"\x01z")
            assert run("display-message", "-p", "-t", source_pane, "#{window_layout}") == layout_before

            # Numbered placement freezes the source, ignores a foreign mark, and
            # keeps focus. Cancelling or choosing this pane never moves anything.
            def cell(pane):
                return run("display-message", "-p", "-t", pane, "#{pane_left}:#{pane_top}")

            def number(pane):
                return run("display-message", "-p", "-t", pane, "#{pane_index}").encode()

            original_cell = cell(source_pane)
            move_readiness = []
            for width in (120, 70):
                fcntl.ioctl(masters[0], termios.TIOCSWINSZ, struct.pack("HHHH", 40, width, 0, 0))
                os.kill(clients[0].pid, signal.SIGWINCH)
                wait_for(lambda: run("display-message", "-p", "-c", actor, "#{client_width}") == str(width))
                original_cell, right_cell = cell(source_pane), cell(right)
                press(b"\x01z")
                output.clear()
                started = time.perf_counter()
                os.write(masters[0], b"\x01m")
                wait_for(lambda: b"Move to pane (Esc cancels)" in clean_output())
                move_readiness.append((time.perf_counter() - started) * 1000)
                assert run("display-message", "-p", "-t", source_pane, "#{window_zoomed_flag}") == "0"
                press(number(right))
                wait_for(lambda: cell(source_pane) == right_cell)
                assert cell(right) == original_cell and context(actor)[1] == source_pane
                assert context(observer) == observer_before and snapshot() == pane_snapshot
                press(b"\x01m")
                press(number(right))
                wait_for(lambda: cell(source_pane) == original_cell)
                for cancel in (b"\x1b", b"\x03"):
                    press(b"\x01m")
                    before_cancel = run("capture-pane", "-p", "-t", source_pane)
                    press(cancel)
                    assert cell(source_pane) == original_cell and snapshot() == pane_snapshot
                    assert run("capture-pane", "-p", "-t", source_pane) == before_cancel
                press(b"\x01m")
                press(number(source_pane))
                assert cell(source_pane) == original_cell and context(actor)[1] == source_pane
            fcntl.ioctl(masters[0], termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
            os.kill(clients[0].pid, signal.SIGWINCH)
            wait_for(lambda: run("display-message", "-p", "-c", actor, "#{client_width}") == "120")

            # Balance neighboring sizes without moving processes between windows.
            lower = next(line.split(":")[0] for line in run("list-panes", "-t", source_pane, "-F",
                         "#{pane_id}:#{pane_left}:#{pane_top}").splitlines()
                         if line.split(":")[1] == original_cell.split(":")[0] and int(line.split(":")[2]) > 0)
            run("resize-pane", "-t", source_pane, "-D", "4")
            press(b"\x01=")
            heights = [int(run("display-message", "-p", "-t", pane, "#{pane_height}")) for pane in (source_pane, lower)]
            assert abs(heights[0] - heights[1]) <= 1, heights
            assert context(actor)[1] == source_pane and context(observer) == observer_before
            assert snapshot() == pane_snapshot

            # Last-pane toggles both ways in the invoking window, even with a
            # globally marked pane elsewhere. Preserve zoom and pane metadata.
            for zoomed in (False, True):
                if zoomed:
                    run("resize-pane", "-Z", "-t", source_pane)
                for expected in (right, source_pane):
                    press(b"\x01p")
                    wait_for(lambda: context(actor)[1] == expected)
                    assert context(observer) == observer_before and snapshot() == pane_snapshot
                    assert run("display-message", "-p", "-t", expected, "#{window_zoomed_flag}") == str(int(zoomed))
                if zoomed:
                    run("resize-pane", "-Z", "-t", source_pane)

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
            # Lift the actual invoking process into a new window, never a marked
            # pane in another session. Repeating on a standalone pane is a no-op.
            old_window = run("display-message", "-p", "-t", source_pane, "#{window_id}")
            press(b"\x01!")
            wait_for(lambda: run("display-message", "-p", "-t", source_pane, "#{window_id}") != old_window)
            assert context(actor) == (source_id, source_pane)
            assert context(observer) == observer_before and snapshot() == pane_snapshot
            assert run("show-option", "-pqv", "-t", source_pane, "@dotfiles_agent_record") == "kept-record"
            assert run("display-message", "-p", "-t", source_pane, "#{window_panes}") == "1"
            lifted_windows = run("list-windows", "-a", "-F", "#{session_id}:#{window_id}")
            press(b"\x01!")
            assert run("list-windows", "-a", "-F", "#{session_id}:#{window_id}") == lifted_windows
            assert context(actor) == (source_id, source_pane) and snapshot() == pane_snapshot

            print("Passed: stable/private keys, assignment/clear/cancel, concurrent writes, malformed state,")
            print("reserved-key migration, e editing, J/K and Shift-arrow ordering, reopened names, letter jumps,")
            print("two-client routing, 120/70-column UI,")
            print("status-name popup, mouse row/wheel/viewport selection, inert headers/drags/editing,")
            print("Last-button history/disabled state and ordinary window-label clicks,")
            print("maximize/zoomed focus, numbered placement/cancel, balance/lift, pane back-and-forth,")
            print("spatial swaps/edges/marked-pane safety and preserved processes/metadata.")
            print("Numbered move first paint {:.1f}/{:.1f} ms at 120/70 columns.".format(*move_readiness))
            print("Mouse-opened picker first paint {:.1f}/{:.1f} ms at 120/70 columns.".format(*mouse_readiness))
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
