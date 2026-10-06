#!/usr/bin/env python3
"""Verify our capture/restore integration with real tmux-resurrect and fake agents."""

import argparse
import json
import os
from pathlib import Path
import runpy
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resurrect', type=Path, default=Path.home() / '.tmux/plugins/tmux-resurrect')
    args = parser.parse_args()
    plugin = args.resurrect.resolve()
    if not (plugin / 'scripts/save.sh').is_file():
        raise SystemExit('Provide the installed tmux-resurrect directory with --resurrect.')
    repo = Path(__file__).resolve().parents[1]
    tmux_exe = shutil.which('tmux')
    if not tmux_exe:
        raise SystemExit('tmux is required.')
    with tempfile.TemporaryDirectory(prefix='dotfiles-recovery-') as temporary:
        root = Path(temporary)
        home = root / 'home (pilot)+'
        tools = home / '.local/bin'
        tools.mkdir(parents=True)
        helper = tools / 'tmux-agent'
        shutil.copyfile(repo / 'home/dot_local/bin/executable_tmux-agent', helper)
        helper.chmod(0o700)
        project = root / 'shared project'
        project.mkdir()
        traces = root / 'traces'
        traces.mkdir()
        socket = root / 'private server.sock'
        env = dict(os.environ, HOME=str(home), XDG_STATE_HOME=str(home / '.local/state'),
                   XDG_CONFIG_HOME=str(home / '.config'), XDG_DATA_HOME=str(home / '.local/share'),
                   PATH=str(tools) + ':/usr/bin:/bin', TERM='xterm-256color',
                   DOTFILES_TMUX_SOCKET=str(socket), DOTFILES_TEST_TRACES=str(traces))
        for key in ('TMUX', 'TMUX_PANE', 'CODEX_HOME', 'CLAUDE_CONFIG_DIR', 'BASH_ENV', 'ENV',
                    'DOTFILES_AGENT_RECORD', 'DOTFILES_AGENT_NONCE'):
            env.pop(key, None)
        (tools / 'python3').symlink_to(sys.executable)
        (tools / 'tmux').symlink_to(tmux_exe)
        stub = '''import json, os, subprocess, sys, time, uuid
from pathlib import Path
name = Path(sys.argv[0]).name
session = (sys.argv[2] if name == 'codex' else sys.argv[2]) if len(sys.argv) > 1 else str(uuid.uuid4())
if os.environ.get('DOTFILES_TEST_MISSING_ID'):
    print('fixture exact ID not found', flush=True)
    sys.exit(1)
payload = {'hook_event_name': 'SessionStart', 'session_id': session, 'cwd': os.getcwd()}
helper = Path.home() / '.local/bin/tmux-agent'
subprocess.run([sys.executable, str(helper), 'capture', name], input=json.dumps(payload), text=True, check=True)
trace = Path(os.environ['DOTFILES_TEST_TRACES']) / (str(os.getpid()) + '.json')
trace.write_text(json.dumps({'agent': name, 'id': session, 'args': sys.argv[1:], 'cwd': os.getcwd(), 'token': os.environ['DOTFILES_AGENT_RECORD']}))
time.sleep(120)
'''
        for tool in ('codex', 'claude'):
            (tools / tool).write_text('#!' + sys.executable + '\n' + stub)
            (tools / tool).chmod(0o700)

        def run(*command, check=True):
            result = subprocess.run([tmux_exe, '-S', str(socket)] + list(command),
                                    env=env, text=True, capture_output=True, timeout=10)
            if check and result.returncode:
                raise AssertionError(result.stderr)
            return result.stdout.rstrip('\n')

        def wait(predicate):
            deadline = time.monotonic() + 5
            while not predicate():
                if time.monotonic() > deadline:
                    raise AssertionError('Synthetic recovery timed out: ' + run('list-panes', '-a', '-F', '#{pane_id} dead=#{pane_dead} status=#{pane_dead_status} signal=#{pane_dead_signal} remain=#{remain-on-exit} pid=#{pane_pid}') + '\n' + '\n'.join(run('capture-pane', '-p', '-t', pane) for pane in run('list-panes', '-a', '-F', '#{pane_id}').splitlines()))
                time.sleep(.02)

        def call(*command, check=True, **overrides):
            result = subprocess.run([sys.executable, str(helper)] + list(command),
                                    env=dict(env, **overrides), capture_output=True, text=True, timeout=10)
            if check and result.returncode:
                raise AssertionError(result.stderr)
            return result

        def start_server():
            run('-f', str(repo / 'home/dot_tmux.conf'), 'new-session', '-d', '-x', '140', '-y', '30', '-s', 'keeper', '-c', str(project), '/bin/sleep 120')
            run('set-option', '-g', 'default-shell', '/bin/bash')
            run('set-option', '-g', 'default-command', '/bin/bash --noprofile --norc')
            run('set-option', '-g', '@resurrect-dir', str(root / 'layouts'))
            # Override home-expanded hook only for this fixture's punctuation-heavy HOME.
            run('set-option', '-g', '@resurrect-hook-post-save-layout',
                shlex.join([sys.executable, str(helper), 'save-layout']))

        def plugin_command(name):
            result = subprocess.run(['/bin/bash', str(plugin / ('scripts/' + name + '.sh')), 'quiet'],
                                    env=dict(env, TMUX=str(socket) + ',1,0'), text=True, capture_output=True, timeout=15)
            if result.returncode or any(line != 'no current client' for line in result.stderr.splitlines()):
                raise AssertionError('Plugin ' + name + ': ' + result.stdout + result.stderr)

        state = home / '.local/state/dotfiles/agents'
        module = runpy.run_path(str(helper))
        try:
            start_server()
            # Settings installation is additive, private, previewable, and idempotent.
            settings = home / '.claude/settings.json'
            settings.parent.mkdir()
            settings.write_text(json.dumps({'theme': 'existing', 'hooks': {'Stop': [{'hooks': []}]}}))
            settings.chmod(0o600)
            before = settings.read_bytes()
            call('setup', '--dry-run')
            assert settings.read_bytes() == before and not (home / '.codex/hooks.json').exists()
            call('setup')
            after = settings.read_bytes()
            call('setup')
            assert settings.read_bytes() == after
            saved_settings = json.loads(after)
            assert saved_settings['theme'] == 'existing' and saved_settings['hooks']['Stop'] == [{'hooks': []}]
            assert len(saved_settings['hooks']['SessionStart']) == 1
            assert settings.stat().st_mode & 0o777 == 0o600
            manifest = list((state.parent / 'backups').glob('agent-hooks-*/manifest.json'))
            assert len(manifest) == 2
            assert any((p.parent / 'settings.json').read_bytes() == before for p in manifest if (p.parent / 'settings.json').exists())
            created = []
            started = time.monotonic()
            for agent, label in (('codex', 'implement'), ('claude', 'review')):
                pane = run('new-window', '-d', '-t', '=keeper:', '-n', label, '-c', str(project), '-P', '-F', '#{pane_id}', '', ';',
                           'set-option', '-w', '-t', '=keeper:=' + label, 'remain-on-exit', 'on')
                run('set-option', '-p', '-t', pane, '@dotfiles_pane_name', label)
                with patch.dict(os.environ, env, clear=True):
                    token = module['register'](pane, agent, directory=str(project))
                run('respawn-pane', '-t', pane, 'exec ' + shlex.join([sys.executable, str(helper), 'start', token]))
                created.append((pane, token, agent, label))
            wait(lambda: len(list(traces.glob('*.json'))) == 2)
            launch_ms = round((time.monotonic() - started) * 1000, 1)
            originals = [json.loads(p.read_text()) for p in traces.glob('*.json')]
            # The pane PID is the CLI itself, with no resident Python supervisor.
            for pane, token, _, _ in created:
                trace = next(p for p in traces.glob('*.json') if json.loads(p.read_text())['token'] == token)
                assert run('display-message', '-p', '-t', pane, '#{pane_pid}') == trace.stem
            assert len({item['id'] for item in originals}) == 2
            for pane, token, agent, label in created:
                data = json.loads((state / 'records' / (token + '.json')).read_text())
                assert data['agent'] == agent and module['valid_id'](data['session_id'])
                assert data['label'] == label and data['cwd'] == str(project)
                assert call('start', token, check=False).returncode != 0  # No duplicate agents.
                wrong = dict(env, DOTFILES_AGENT_RECORD=token, DOTFILES_AGENT_NONCE='stale')
                subprocess.run([sys.executable, str(helper), 'capture', agent], env=wrong,
                               input=json.dumps({'hook_event_name': 'SessionStart', 'session_id': str(uuid.uuid4())}), text=True, check=True)
                assert json.loads((state / 'records' / (token + '.json')).read_text())['session_id'] == data['session_id']
            # Freeze conversation IDs at save time; later /clear cannot change old snapshots.
            started = time.monotonic()
            plugin_command('save')
            save_ms = round((time.monotonic() - started) * 1000, 1)
            layout = root / 'layouts/last'
            saved = layout.read_text()
            assert sum('resume' in shlex.split(line.split('\t')[-1][1:]) for line in saved.splitlines() if line.startswith('pane\t')) == 2
            assert ' start ' not in saved
            assert 'sleep' in saved  # Unmanaged pane remains unchanged.
            snapshots = list((state / 'snapshots').glob('*.json'))
            assert len(snapshots) == 2
            for snapshot in snapshots:
                duplicate = call('resume', snapshot.stem, check=False)
                assert duplicate.returncode != 0 and 'already running' in duplicate.stderr
            assert len(list(traces.glob('*.json'))) == 2
            assert all(json.loads(p.read_text())['cwd'] == str(project) for p in snapshots), [p.read_text() for p in snapshots]
            for _, token, agent, _ in created:
                record = state / 'records' / (token + '.json')
                data = json.loads(record.read_text())
                subprocess.run([sys.executable, str(helper), 'capture', agent],
                               env=dict(env, DOTFILES_AGENT_RECORD=token, DOTFILES_AGENT_NONCE=data['nonce']),
                               input=json.dumps({'hook_event_name': 'SessionStart', 'source': 'clear',
                                                 'session_id': str(uuid.uuid4())}), text=True, check=True)
                assert json.loads(record.read_text())['session_id'] != data['session_id']
            assert {json.loads(p.read_text())['session_id'] for p in snapshots} == {item['id'] for item in originals}
            # A process restart, on a private socket, must resume exactly the saved IDs.
            run('kill-server')
            time.sleep(.1)  # Let the private server finish unlinking its socket.
            start_server()
            keeper = run('list-panes', '-a', '-F', '#{pane_id}:#{pane_pid}')
            started = time.monotonic()
            plugin_command('restore')
            wait(lambda: len(list(traces.glob('*.json'))) == 4)
            restore_ms = round((time.monotonic() - started) * 1000, 1)
            records = [json.loads(p.read_text()) for p in traces.glob('*.json')]
            resumed = [item for item in records if item['args']]
            assert {(x['agent'], x['id']) for x in resumed} == {(x['agent'], x['id']) for x in originals}
            assert all(x['args'] == (['resume', x['id']] if x['agent'] == 'codex' else ['--resume', x['id']]) for x in resumed)
            assert all(x['cwd'] == str(project) for x in resumed)
            assert keeper in run('list-panes', '-a', '-F', '#{pane_id}:#{pane_pid}')
            for _, token, _, label in created:
                assert label in run('list-panes', '-a', '-F', '#{@dotfiles_pane_name}')
            running = run('list-panes', '-a', '-F', '#{pane_id}:#{pane_pid}')
            plugin_command('restore')
            assert run('list-panes', '-a', '-F', '#{pane_id}:#{pane_pid}') == running
            assert len(list(traces.glob('*.json'))) == 4
            # No ID, missing CLI, absent directory, and stale IDs must never launch fresh.
            run('kill-server')
            time.sleep(.1)  # Let the private server finish unlinking its socket.
            start_server()
            sample = json.loads(snapshots[0].read_text())
            with patch.dict(os.environ, env, clear=True):
                for change in ({'session_id': None}, {'cwd': str(root / 'gone')}, {}):
                    bad = dict(sample, **change)
                    digest = 'f' * 64
                    module['write_json'](module['snapshot_path'](digest), bad)
                    result = call('resume', digest, check=False, DOTFILES_TEST_MISSING_ID='1')
                    assert result.returncode != 0
                executable = tools / sample['agent']
                executable.rename(executable.with_suffix('.missing'))
                assert call('resume', snapshots[0].stem, check=False).returncode != 0
                executable.with_suffix('.missing').rename(executable)
            assert len(list(traces.glob('*.json'))) == 4
            with patch.dict(os.environ, env, clear=True):
                module['write_json'](module['snapshot_path']('e' * 64), dict(sample, session_id=None))
            failed = run('new-window', '-d', '-t', '=keeper:', '-n', 'missing-id', '-c', str(project),
                         '-P', '-F', '#{pane_id}',
                         'exec ' + shlex.join([sys.executable, str(helper), 'resume', 'e' * 64]), ';',
                         'set-option', '-w', '-t', '=keeper:=missing-id', 'remain-on-exit', 'on')
            wait(lambda: run('display-message', '-p', '-t', failed, '#{pane_dead}') == '1')
            assert run('display-message', '-p', '-t', failed, '#{pane_dead_status}') in ('', '1')
            assert 'No exact conversation ID' in run('capture-pane', '-p', '-S', '-100', '-t', failed)
            assert len(list(traces.glob('*.json'))) == 4
            run('kill-window', '-t', failed)
            # Explicit adoption never replaces the existing process; readiness is reported.
            pane, pid = run('list-panes', '-a', '-F', '#{pane_id}:#{pane_pid}').split(':')
            call('bind', 'codex', str(uuid.uuid4()), '--pane', pane)
            assert run('display-message', '-p', '-t', pane, '#{pane_pid}') == pid
            assert 'manual binding' in call('status').stdout
            call('bind', 'codex', str(uuid.uuid4()), '--pane', pane)
            for directory in ('records', 'snapshots', 'locks'):
                assert (state / directory).stat().st_mode & 0o777 == 0o700
            assert all(p.stat().st_mode & 0o777 == 0o600 for p in state.rglob('*') if p.is_file())
            print(json.dumps({'result': 'passed', 'synthetic_two_agent_launch_ms': launch_ms,
                              'plugin_save_ms': save_ms, 'plugin_restore_ms': restore_ms,
                              'real_agent_or_reboot': False}, indent=2))
        finally:
            run('kill-server', check=False)


if __name__ == '__main__':
    main()
