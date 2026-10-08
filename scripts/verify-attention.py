#!/usr/bin/env python3
"""Verify our event reducer, adapters and tmux UI with isolated synthetic agents.

No real conversations, provider calls, live tmux changes or agent input. Native
payload fixtures check our translations; installed-harness delivery needs its own
probe and is deliberately not implied by this script.
"""

from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
import os
from pathlib import Path
import pty
import runpy
import select
import shlex
import shutil
import statistics
import struct
import subprocess
import sys
import tempfile
import termios
import time
import uuid
from unittest.mock import patch


def main():
    repo = Path(__file__).resolve().parents[1]
    tmux = shutil.which('tmux')
    if not tmux or not shutil.which('fzf'):
        raise SystemExit('tmux and fzf are required.')
    with tempfile.TemporaryDirectory(prefix='dotfiles-attention-') as temporary:
        root = Path(temporary)
        home = root / "home ' quoted"
        tools = home / '.local/bin'
        tools.mkdir(parents=True)
        for name in ('tmux-agent', 'tmux-attention', 'tmux-tasks'):
            path = tools / name
            shutil.copyfile(repo / 'home/dot_local/bin' / ('executable_' + name), path)
            path.chmod(0o700)
        shutil.copyfile(repo / 'home/dot_local/bin/tmux_keys.py', tools / 'tmux_keys.py')
        for name, executable in (('tmux', tmux), ('python3', sys.executable), ('fzf', shutil.which('fzf'))):
            (tools / name).symlink_to(executable)
        traces = root / 'traces'
        traces.mkdir(mode=0o700)
        socket = root / 'private.sock'
        env = dict(os.environ, HOME=str(home), PATH=str(tools) + ':/usr/bin:/bin',
                   XDG_STATE_HOME=str(home / '.local/state'), TERM='xterm-256color',
                   DOTFILES_TMUX_SOCKET=str(socket), DOTFILES_TEST_TRACES=str(traces))
        for key in ('TMUX', 'TMUX_PANE', 'CODEX_HOME', 'CLAUDE_CONFIG_DIR', 'BASH_ENV', 'ENV',
                    'DOTFILES_AGENT_RECORD', 'DOTFILES_AGENT_NONCE', 'DOTFILES_TMUX_CLIENT'):
            env.pop(key, None)
        fake = '''import json, os, subprocess, sys, time, uuid
from pathlib import Path
agent = Path(sys.argv[0]).name
session = sys.argv[2] if len(sys.argv) > 1 else str(uuid.uuid4())
payload = dict(hook_event_name='SessionStart', session_id=session)
subprocess.run([sys.executable, str(Path.home()/'.local/bin/tmux-agent'), 'capture', agent],
               input=json.dumps(payload), text=True, check=True)
path = Path(os.environ['DOTFILES_TEST_TRACES']) / (os.environ['TMUX_PANE'][1:] + '.json')
pending = path.with_suffix('.tmp')
pending.write_text(json.dumps(dict(env=dict(os.environ), agent=agent, session=session)))
pending.chmod(0o600)
pending.replace(path)
print('synthetic agent ready', flush=True)
time.sleep(120)
'''
        for name in ('codex', 'claude'):
            (tools / name).write_text('#!' + sys.executable + '\n' + fake)
            (tools / name).chmod(0o700)
        attention = tools / 'tmux-attention'
        agent = runpy.run_path(str(tools / 'tmux-agent'))
        clients = []
        output = bytearray()

        def run(*args):
            result = subprocess.run([tmux, '-S', str(socket)] + list(args), env=env,
                                    capture_output=True, text=True, timeout=5)
            if result.returncode:
                raise AssertionError(result.stderr)
            return result.stdout.rstrip('\n')

        def call(*args, data=None, environment=None):
            result = subprocess.run([sys.executable, str(attention)] + list(args),
                                    env=environment or env, input=json.dumps(data) if data is not None else '',
                                    capture_output=True, text=True, timeout=5)
            if result.returncode:
                raise AssertionError(result.stderr)
            return result.stdout.strip()

        def drain(duration=.02):
            deadline = time.monotonic() + duration
            while clients and time.monotonic() < deadline:
                descriptors = [master for master, _ in clients]
                for master in select.select(descriptors, [], [], .01)[0]:
                    try:
                        data = os.read(master, 65536)
                        if master == clients[0][0]:
                            output.extend(data)
                            del output[:-20000]
                    except OSError:
                        pass

        def wait(predicate):
            deadline = time.monotonic() + 5
            while not predicate():
                if time.monotonic() >= deadline:
                    raise AssertionError('Timed out; fixture terminal tail: ' + repr(bytes(output[-1200:])))
                drain()

        def state(pane):
            raw = run('show-options', '-pqv', '-t', pane, '@dotfiles_attention_state')
            return json.loads(raw) if raw else {}

        def trace(pane):
            path = traces / (pane[1:] + '.json')
            try:
                wait(path.exists)
            except AssertionError as error:
                raise AssertionError(str(error) + '\n' + run('capture-pane', '-p', '-t', pane)) from error
            return json.loads(path.read_text())

        def start(name):
            pane = run('new-window', '-d', '-t', '=pilot:', '-n', name, '-P', '-F', '#{pane_id}', '/bin/sleep 120')
            with patch.dict(os.environ, env, clear=True):
                token = agent['register'](pane, name)
            run('set-option', '-p', '-t', pane, '@dotfiles_agent', name)
            run('set-option', '-p', '-t', pane, '@dotfiles_pane_name', name)
            run('respawn-pane', '-k', '-t', pane,
                shlex.join([sys.executable, str(tools / 'tmux-agent'), 'start', token]))
            fixture = trace(pane)
            assert state(pane)['phase'] == 'unknown'
            return pane, fixture

        def hook(pane, fixture, name, **fields):
            payload = dict(hook_event_name=name, session_id=fixture['session'], **fields)
            assert call('hook', fixture['agent'], data=payload, environment=fixture['env']) == '{}'
            return state(pane)

        def report(pane, fixture, event, **fields):
            call('report', data=dict(version=1, session_id=fixture['session'], event=event, **fields), environment=fixture['env'])
            return state(pane)

        def active(client):
            for row in run('list-clients', '-F', '#{client_name}\t#{pane_id}').splitlines():
                name, pane = row.split('\t')
                if name == client:
                    return pane
            raise AssertionError('Fixture client detached.')

        def attach(session, width=120):
            before = set(run('list-clients', '-F', '#{client_name}').splitlines())
            master, slave = pty.openpty()
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 40, width, 0, 0))
            process = subprocess.Popen([tmux, '-S', str(socket), 'attach-session', '-t', '=' + session],
                                       env=env, stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
            os.close(slave)
            clients.append((master, process))
            wait(lambda: set(run('list-clients', '-F', '#{client_name}').splitlines()) - before)
            drain(.15)
            return next(iter(set(run('list-clients', '-F', '#{client_name}').splitlines()) - before))

        def press(keys):
            if keys.startswith(b'\x01') and len(keys) == 2:
                os.write(clients[0][0], b'\x01')
                wait(lambda: any(row == client + '\t1' for row in
                     run('list-clients', '-F', '#{client_name}\t#{client_prefix}').splitlines()))
                keys = keys[1:]
            os.write(clients[0][0], keys)
            drain(.08)

        try:
            run('-f', str(repo / 'home/dot_tmux.conf'), 'new-session', '-d', '-s', 'pilot', '-x', '120', '-y', '40', '/bin/sleep 120')
            run('set-option', '-g', 'default-shell', '/bin/sh')
            keeper = run('display-message', '-p', '#{pane_id}')
            # Bootstrap preview, additive merge, mixed hook preservation, reruns,
            # private modes and restorable originals belong to our implementation.
            settings = home / '.claude/settings.json'
            settings.parent.mkdir()
            existing = {'theme': 'existing', 'hooks': {'Stop': [{'hooks': [
                {'type': 'command', 'command': 'true'},
                {'type': 'command', 'command': 'python3 "$HOME/.local/bin/tmux-attention" hook claude'}]}]}}
            settings.write_text(json.dumps(existing))
            settings.chmod(0o600)
            original = settings.read_bytes()
            call('setup', '--dry-run')
            assert settings.read_bytes() == original and not (home / '.codex/hooks.json').exists()
            call('setup')
            saved = settings.read_bytes()
            assert json.loads(saved)['theme'] == 'existing'
            assert json.loads(saved)['hooks']['Stop'][0]['hooks'][0]['command'] == 'true'
            backups = list((home / '.local/state/dotfiles/backups').glob('attention-hooks-*/manifest.json'))
            assert len(backups) == 2
            call('setup')
            assert settings.read_bytes() == saved
            assert len(list((home / '.local/state/dotfiles/backups').glob('attention-hooks-*/manifest.json'))) == 2
            for manifest in backups:
                assert manifest.stat().st_mode & 0o777 == 0o600
                meta = json.loads(manifest.read_text())
                if meta['existed']:
                    assert (manifest.parent / Path(meta['target']).name).read_bytes() == original

            codex, cf = start('codex')
            claude, lf = start('claude')
            original_pids = run('list-panes', '-a', '-F', '#{pane_id}:#{pane_pid}')
            hook(codex, cf, 'UserPromptSubmit', turn_id='c1')
            assert state(codex)['phase'] == 'working'
            hook(codex, cf, 'PermissionRequest', tool_name='exec_command', turn_id='c1')
            notice = state(codex)['notice']['id']
            hook(codex, cf, 'PermissionRequest', tool_name='exec_command', turn_id='c1')
            assert state(codex)['notice']['id'] == notice
            call('seen', '--pane', codex, '--notice', notice)
            assert state(codex)['notice']['seen'] and state(codex)['requests']
            assert run('show-options', '-pqv', '-t', codex, '@dotfiles_attention_kind') == 'input'
            hook(codex, cf, 'Stop', turn_id='c1')
            assert state(codex)['requests'] and state(codex)['phase'] == 'waiting'
            hook(codex, cf, 'PostToolUse', tool_name='exec_command', turn_id='stale')
            assert state(codex)['requests']
            hook(codex, cf, 'PostToolUse', tool_name='exec_command', turn_id='c1')
            assert state(codex)['phase'] == 'working' and not state(codex)['requests']
            hook(codex, cf, 'Stop', turn_id='c1', agent_id='child')
            assert not state(codex)['notice']
            hook(codex, cf, 'Stop', turn_id='c1')
            ready = state(codex)['notice']['id']
            hook(codex, cf, 'Stop', turn_id='c1')
            assert state(codex)['notice']['id'] == ready
            hook(codex, cf, 'PostToolUse', turn_id='c1', tool_name='exec_command')
            assert not state(codex)['notice']  # Stop hook continuation.
            hook(codex, cf, 'UserPromptSubmit', turn_id='c2')
            hook(codex, cf, 'Stop', turn_id='c1')
            assert state(codex)['phase'] == 'working'
            hook(codex, cf, 'Interrupt', turn_id='c2')
            assert state(codex)['phase'] == 'interrupted' and not state(codex)['notice']

            hook(claude, lf, 'UserPromptSubmit')
            for notification in ('idle_prompt', 'auth_success', 'teammate_idle'):
                hook(claude, lf, 'Notification', notification_type=notification)
            assert state(claude)['phase'] == 'working'
            hook(claude, lf, 'PreToolUse', tool_name='AskUserQuestion', tool_use_id='q1')
            hook(claude, lf, 'Notification', notification_type='elicitation_dialog')
            hook(claude, lf, 'PostToolUse', tool_name='AskUserQuestion', tool_use_id='q1')
            assert not state(claude)['requests']
            hook(claude, lf, 'Elicitation', elicitation_id='e1')
            hook(claude, lf, 'ElicitationResult', elicitation_id='e1')
            assert state(claude)['phase'] == 'working'
            hook(claude, lf, 'Notification', notification_type='elicitation_dialog')
            hook(claude, lf, 'ElicitationResult', elicitation_id='fallback')
            assert state(claude)['phase'] == 'working'
            hook(claude, lf, 'PermissionRequest', tool_name='Bash')
            hook(claude, lf, 'Notification', notification_type='permission_prompt')
            assert len(state(claude)['requests']) == 1
            hook(claude, lf, 'PostToolUseFailure', tool_name='Bash', tool_use_id='b1')
            assert state(claude)['phase'] == 'working' and not state(claude)['notice']
            hook(claude, lf, 'Stop', background_tasks=[{'id': 'job'}])
            assert state(claude)['phase'] == 'background' and not state(claude)['notice']
            hook(claude, lf, 'Stop', background_tasks=[])
            assert state(claude)['notice']['kind'] == 'ready'
            hook(claude, lf, 'UserPromptSubmit')
            hook(claude, lf, 'StopFailure')
            assert state(claude)['notice']['kind'] == 'error'

            # Generic reports exercise the shared contract independently of native
            # event names. Concurrent requests serialize without lost updates.
            report(codex, cf, 'turn_started', turn_id='c3')
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lambda i: report(codex, cf, 'input_requested', turn_id='c3',
                                             request_id='r' + str(i), reason='question'), range(4)))
            assert len(state(codex)['requests']) == 4
            for i in range(4):
                report(codex, cf, 'input_resolved', turn_id='c3', request_id='r' + str(i))
            assert state(codex)['phase'] == 'working'
            before = state(codex)
            for key, value in (('DOTFILES_AGENT_NONCE', str(uuid.uuid4())), ('TMUX_PANE', keeper)):
                stale = dict(cf['env'], **{key: value})
                call('hook', 'codex', data=dict(hook_event_name='Stop', session_id=cf['session'], turn_id='c3'), environment=stale)
                assert state(codex) == before
            call('hook', 'codex', data=dict(hook_event_name='Stop', session_id=str(uuid.uuid4())), environment=cf['env'])
            assert state(codex) == before
            # Session/turn text and tool outputs never reach state or UI.
            hook(codex, cf, 'PostToolUse', tool_name='exec_command', turn_id='c3',
                 tool_input={'command': 'PRIVATE FIXTURE SECRET'}, tool_response='PRIVATE FIXTURE SECRET')
            assert 'PRIVATE FIXTURE SECRET' not in json.dumps(state(codex))

            # Two clients, linked windows, hidden pending input, response visits,
            # explicit seen actions, previous-task history and width-aware status.
            run('new-session', '-d', '-s', 'observer', '/bin/sleep 120')
            run('link-window', '-s', '=pilot:2', '-t', '=observer:2')
            hook(codex, cf, 'PermissionRequest', turn_id='c3', tool_name='exec_command')
            run('set-option', '-p', '-t', codex, '@dotfiles_task_archived', '1')
            assert '1 input' in run('show-options', '-gqv', '@dotfiles_attention_summary')
            client = attach('pilot')
            observer = attach('observer', 70)
            observer_pane = active(observer)
            run('switch-client', '-c', client, '-t', keeper)
            drain(.1)
            output.clear()
            started = time.perf_counter()
            press(b'\x01A')
            wait(lambda: b'Attention >' in output and b'Alt+m' in output)
            popup_ms = (time.perf_counter() - started) * 1000
            press(b'codex\r')
            wait(lambda: active(client) == codex)
            assert state(codex)['notice']['seen'] and state(codex)['requests']
            assert active(observer) == observer_pane
            press(b'\x01a')
            wait(lambda: active(client) == claude and state(claude)['notice']['seen'])
            assert state(claude)['phase'] == 'failed'
            hook(claude, lf, 'UserPromptSubmit')
            hook(claude, lf, 'Stop')
            run('switch-client', '-c', client, '-t', keeper)
            output.clear()
            press(b'\x01g')
            wait(lambda: b'Alt+u' in output)
            press(b'\x1bu')
            wait(lambda: b'Attention >' in output)
            press(b'claude\x1bm')
            wait(lambda: state(claude)['notice']['seen'])
            press(b'\x1b')
            drain(.2)
            assert active(client) == keeper
            assert state(codex)['requests']
            report(codex, cf, 'input_resolved', turn_id='c3', request_id='permission:exec_command')
            hook(codex, cf, 'Stop', turn_id='c3')
            run('switch-client', '-c', client, '-t', keeper)
            press(b'\x01a')
            wait(lambda: active(client) == codex and state(codex)['notice']['seen'])
            wait(lambda: not run('show-options', '-gqv', '@dotfiles_attention_summary'))
            press(b'\x01B')
            wait(lambda: active(client) == keeper)
            assert set(original_pids.splitlines()) == {row for row in run('list-panes', '-a', '-F', '#{pane_id}:#{pane_pid}').splitlines()
                                                       if row.split(':')[0] in (keeper, codex, claude)}
            widths = dict(row.split('\t') for row in run('list-clients', '-F', '#{client_name}\t#{client_width}').splitlines())
            assert widths[client] == '120' and widths[observer] == '70'
            # Exit/respawn discards cached attention even if no CLI end hook ran.
            hook(claude, lf, 'UserPromptSubmit')
            hook(claude, lf, 'PermissionRequest', tool_name='Bash')
            run('respawn-pane', '-k', '-t', claude, '/bin/sleep 120')
            call('refresh')
            assert not state(claude)
            stale = dict(lf['env'])
            call('hook', 'claude', data=dict(hook_event_name='Stop', session_id=lf['session']), environment=stale)
            assert not state(claude)
            hook(codex, cf, 'UserPromptSubmit', turn_id='c4')
            samples = []
            for _ in range(7):
                started = time.perf_counter()
                hook(codex, cf, 'PostToolUse', turn_id='c4', tool_name='exec_command')
                samples.append((time.perf_counter() - started) * 1000)
            lock_files = list((home / '.local/state/dotfiles/attention').glob('*.lock'))
            assert lock_files and all(path.stat().st_mode & 0o777 == 0o600 for path in lock_files)
            server_pid = run('display-message', '-p', '#{pid}')
            def ticks():
                values = Path('/proc/' + server_pid + '/stat').read_text().rpartition(') ')[2].split()
                return int(values[11]) + int(values[12])
            before_ticks = ticks()
            time.sleep(1)
            idle_cpu = (ticks() - before_ticks) / os.sysconf('SC_CLK_TCK') * 100
            hook(codex, cf, 'PermissionRequest', turn_id='c4', tool_name='exec_command')
            assert '1 input' in run('show-options', '-gqv', '@dotfiles_attention_summary')
            run('kill-pane', '-t', codex)
            wait(lambda: not run('show-options', '-gqv', '@dotfiles_attention_summary'))
            print('Passed: reducer/adapters, identity guards, concurrent updates, hook merging/backups, native counts, linked/hidden panes, two-client attention UI, acknowledgement and process preservation.')
            print('Synthetic event + state read median %.1f ms; attention popup %.1f ms.' % (statistics.median(samples), popup_ms))
            print('One-second server idle CPU sample: %.1f%%; no attention daemon or polling.' % idle_cpu)
        finally:
            subprocess.run([tmux, '-S', str(socket), 'kill-server'], env=env, capture_output=True)
            for master, process in clients:
                process.wait(timeout=5)
                os.close(master)


if __name__ == '__main__':
    main()
