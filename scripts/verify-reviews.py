#!/usr/bin/env python3
"""Verify private reviews with real tuicr and fake agents on a private tmux server."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import pty
import re
import runpy
import select
import signal
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import termios
import time
import uuid
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tuicr', default=shutil.which('tuicr'))
    args = parser.parse_args()
    if not args.tuicr or not shutil.which('tmux') or not shutil.which('git'):
        raise SystemExit('tmux, Git and tuicr are required')
    if not sys.platform.startswith('linux'):
        raise SystemExit('The fake-agent process-name fixture currently requires Linux.')
    repo = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, str(repo / 'scripts/sync-tmux-keys.py'), '--check'], check=True)
    with tempfile.TemporaryDirectory(prefix='dotfiles-reviews-') as temporary:
        root = Path(temporary)
        home = root / "home ' space"
        tools = home / '.local/bin'
        tools.mkdir(parents=True)
        for source in (repo / 'home/dot_local/bin').iterdir():
            if not source.is_file():
                continue
            name = source.name[len('executable_'):] if source.name.startswith('executable_') else source.name
            shutil.copyfile(source, tools / name)
            (tools / name).chmod(0o700)
        for name, path in [('tmux', shutil.which('tmux')), ('git', shutil.which('git')),
                           ('python3', sys.executable), ('less', shutil.which('less')),
                           ('tuicr', str(Path(args.tuicr).resolve()))]:
            (tools / name).symlink_to(path)
        config = home / '.config/tuicr'
        config.mkdir(parents=True)
        shutil.copyfile(repo / 'home/dot_config/tuicr/config.toml', config / 'config.toml')
        env = os.environ.copy()
        for key in ('TMUX', 'TMUX_PANE', 'BASH_ENV', 'ENV', 'CODEX_HOME', 'CLAUDE_CONFIG_DIR'):
            env.pop(key, None)
        env.update(HOME=str(home), PATH=str(tools), TERM='xterm-256color',
                   XDG_CONFIG_HOME=str(home / '.config'), XDG_DATA_HOME=str(home / '.local/share'),
                   XDG_STATE_HOME=str(home / '.local/state'), XDG_CACHE_HOME=str(home / '.cache'),
                   GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_SYSTEM='/dev/null',
                   DOTFILES_REVIEW_EDITOR_RESULT=str(root / 'editor.json'))
        project = root / "project #$(touch injected); ' space"
        project.mkdir()
        def git(*argv):
            result = subprocess.run([shutil.which('git'), '-C', str(project)] + list(argv),
                                    env=env, capture_output=True, text=True, timeout=5)
            assert result.returncode == 0, result.stderr
            return result.stdout.strip()
        git('init', '-q')
        (home / '.gitignore_global').write_text('ignored.generated\n')
        (project / 'ignored.generated').write_text('synthetic ignored artifact\n')
        git('config', '--file', str(home / '.gitconfig'), 'core.excludesFile', '~/.gitignore_global')
        env['GIT_CONFIG_GLOBAL'] = str(home / '.gitconfig')
        file = project / 'demo.py'
        file.write_text('def compute():\n    first = 1\n    second = 2\n    return first + second\n')
        git('add', 'demo.py')
        git('-c', 'user.name=Review Test', '-c', 'user.email=review@example.invalid', 'commit', '-qm', 'fixture')
        file.write_text('def compute():\n    first = 7\n    second = 9\n    return first - second\n')
        (tools / 'nvim').write_text('#!' + sys.executable + '\nimport json,os,sys\n'
                                  'open(os.environ["DOTFILES_REVIEW_EDITOR_RESULT"],"w").write('
                                  'json.dumps({"home":os.environ["HOME"],"data":os.environ.get("XDG_DATA_HOME"),"args":sys.argv[1:]}))\n')
        (tools / 'nvim').chmod(0o700)
        raw_agent = ('import ctypes,os,sys,tty\n'
                     'ctypes.CDLL(None).prctl(15,sys.argv[2].encode(),0,0,0)\n'
                     'tty.setraw(0)\nos.write(1,b"\\x1b[?2004hAGENT READY")\n'
                     'with open(sys.argv[1],"wb",buffering=0) as output:\n'
                     '    while True:\n        data=os.read(0,65536)\n        if not data:break\n        output.write(data)\n')
        for agent in ('codex', 'claude'):
            # Give the interpreter the CLI's argv[0], as tmux reads cmdline.
            (tools / agent).write_text('#!' + sys.executable + '\nimport os,sys\n'
                + 'agent=os.path.basename(sys.argv[0])\n'
                + 'os.execv(sys.executable,[agent,"-c",' + repr(raw_agent) + ',sys.argv[1],agent])\n')
            (tools / agent).chmod(0o700)
        socket = root / 'server.sock'
        command = [shutil.which('tmux'), '-S', str(socket)]
        env['DOTFILES_TMUX_SOCKET'] = str(socket)
        master, client = None, None
        output = bytearray()
        fragmented_markers = []
        def run(*argv):
            result = subprocess.run(command + list(argv), env=env, capture_output=True, text=True, timeout=5)
            if result.returncode:
                raise AssertionError(result.stderr)
            return result.stdout.rstrip('\n')
        def drain(duration=0.06):
            end = time.monotonic() + duration
            while time.monotonic() < end:
                if master is not None and select.select([master], [], [], 0.01)[0]:
                    try:
                        output.extend(os.read(master, 65536))
                        del output[:-20000]
                    except OSError:
                        break
        def wait(predicate):
            end = time.monotonic() + 6
            while time.monotonic() < end:
                if predicate():return
                drain(0.02)
            raise AssertionError('Timed out: ' + repr(bytes(output[-2400:])))
        def press(data):
            os.write(master, data)
            drain(0.1)
        def active():
            rows = run('list-clients', '-F', '#{client_name}\t#{session_id}:#{window_id}.#{pane_id}')
            return next(row.split('\t')[1] for row in rows.splitlines() if row.split('\t')[0] == client_name)
        def readable_output():
            # tmux may insert cursor/style sequences between printed characters.
            # Waiting for a contiguous raw word can wait until a later redraw.
            text = re.sub(rb'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)', b'', bytes(output))
            text = re.sub(rb'\x1b\[[0-?]*[ -/]*[@-~]', b'', text)
            return re.sub(rb'\x1b[()][0-9A-Za-z]', b'', text)
        def open_review(target):
            output.clear()
            start = time.perf_counter()
            popup = ['display-popup', '-EE', '-c', client_name, '-w', '95%', '-h', '90%', '-T', 'Local review',
                     '-e', 'DOTFILES_TMUX_CLIENT=' + client_name,
                     '-e', 'DOTFILES_TMUX_SOCKET=' + str(socket), '-e', 'DOTFILES_TMUX_PANE=' + target,
                     'exec ' + shlex.quote(str(tools / 'tmux-review'))]
            run('run-shell', '-b', '-C', shlex.join(popup).replace('#', '##'))
            wait(lambda: b'demo.py' in readable_output())
            fragmented_markers.append(b'demo.py' not in output)
            return (time.perf_counter() - start) * 1000
        def add_comment(text, kind='line'):
            press(b';l')
            press(b';l')
            press(b':2\r')
            if kind == 'range':
                press(b'v')
                press(b'j')
            press(b'C' if kind == 'file' else b'c')
            wait(lambda: b'comment' in output.lower())
            press(text.encode())
            press(b'\x13')
        def finish():
            output.clear()
            press(b'ZZ')
            wait(lambda: b'Feedback saved privately' in output)
            return sorted((home / '.local/state/dotfiles/reviews').glob('*/*.json'), key=lambda path:path.stat().st_mtime_ns)[-1]
        try:
            run('-f', str(repo / 'home/dot_tmux.conf'), 'new-session', '-d', '-s', 'source',
                '-c', str(project).replace('#', '##'), '-x', '120', '-y', '40', '/bin/sleep 180')
            run('set-option', '-g', 'default-shell', '/bin/sh')
            source = run('display-message', '-p', '#{session_id}:#{window_id}.#{pane_id}')
            agents = {}
            for agent in ('codex', 'claude'):
                input_file = root / (agent + '.input')
                target = run('new-window', '-d', '-n', agent, '-c', str(project).replace('#', '##'),
                             '-P', '-F', '#{session_id}:#{window_id}.#{pane_id}',
                             'exec ' + shlex.join([str(tools / agent), str(input_file)]))
                conversation = str(uuid.uuid4())
                subprocess.run([sys.executable, str(tools / 'tmux-agent'), 'bind', agent, conversation,
                                '--pane', target.rsplit('.',1)[1]], env=env, capture_output=True, check=True)
                agents[agent] = (target, conversation, input_file)
                wait(lambda: run('display-message', '-p', '-t', target, '#{pane_current_command}') == agent)
            original = run('list-panes', '-a', '-F', '#{pane_id}:#{pane_pid}')
            master, slave = pty.openpty()
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH',40,120,0,0))
            client = subprocess.Popen(command + ['attach-session', '-t', '=source'], env=env,
                                      stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
            os.close(slave)
            wait(lambda: run('list-clients', '-F', '#{client_name}'))
            client_name = run('list-clients', '-F', '#{client_name}')
            drain(0.2)
            env['DOTFILES_TMUX_CLIENT'] = client_name
            with patch.dict(os.environ, env, clear=True):
                review = runpy.run_path(str(tools / 'tmux-review'))
                assert review['review_environment'](root / 'env-check')['HOME'] == str(home)
                codex = review['selected'](run, client_name, agents['codex'][0])
                claude = review['selected'](run, client_name, agents['claude'][0])
                assert review['task_directory'](codex, str(socket)) != review['task_directory'](claude, str(socket))
                start = time.perf_counter()
                revision = review['revision'](str(project))
                revision_ms = (time.perf_counter()-start)*1000
                untracked = project / 'new.txt'
                untracked.write_text('first')
                first = review['revision'](str(project))
                untracked.write_text('other')
                assert first != review['revision'](str(project))
                untracked.unlink()
                assert review['revision'](str(project)) == revision
                with patch.dict(os.environ, XDG_STATE_HOME=str(project / 'private')):
                    try:review['state_root']()
                    except ValueError:pass
                    else:raise AssertionError('Review state allowed inside Git')
                    assert not (project / 'private').exists()
            # Per-agent comments never cross between two agents in one checkout.
            open_review(agents['claude'][0])
            assert b'ignored.generated' not in readable_output()
            add_comment('CLAUDE ONLY')
            claude_context = json.loads(finish().read_text())
            press(b'q')
            drain(0.15)
            popup_ms = open_review(agents['codex'][0])
            # Measure the open review, including tuicr/helper and synthetic agents.
            server = int(run('display-message', '-p', '#{pid}'))
            def cpu_ticks():
                processes = {}
                for entry in Path('/proc').iterdir():
                    if not entry.name.isdigit():
                        continue
                    try:
                        stat = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
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
            drain(0.2)
            ticks = cpu_ticks()
            started = time.monotonic()
            drain(1)
            idle_percent = round((cpu_ticks() - ticks) / os.sysconf('SC_CLK_TCK')
                                 / (time.monotonic() - started) * 100, 2)
            add_comment('CODEX RANGE', 'range')
            add_comment('CODEX LINE')
            add_comment('CODEX FILE', 'file')
            press(b'e')
            wait(lambda: (root / 'editor.json').exists())
            editor = json.loads((root / 'editor.json').read_text())
            assert editor['home'] == str(home) and editor['data'] == env['XDG_DATA_HOME'], editor
            context_file = finish()
            context = json.loads(context_file.read_text())
            markdown = Path(context['feedback']).read_text()
            assert all(text in markdown for text in ('CODEX LINE','CODEX RANGE','CODEX FILE','demo.py:2','demo.py:2-3')), markdown
            assert 'CLAUDE ONLY' not in markdown
            assert claude_context['conversation'] != context['conversation']
            assert '\x1b' not in markdown
            assert active() == source
            # View action returns cleanly to the same feedback menu.
            press(b'v');drain(0.15);press(b'q')
            wait(lambda: b'Feedback saved privately' in output)
            # New checkout content blocks handoff; original agent receives nothing.
            file.write_text(file.read_text()+'# new work\n')
            press(b'p')
            wait(lambda: b'checkout changed' in output.lower())
            assert all(not path.read_bytes() for _,_,path in agents.values())
            file.write_text(file.read_text().replace('# new work\n',''))
            # A new exact conversation ID blocks routing even when pane is unchanged.
            with patch.dict(os.environ, env, clear=True):
                recovery = runpy.run_path(str(tools / 'tmux-agent'))
                record_path = recovery['record_path'](context['record'])
                record = recovery['read_json'](record_path)
                changed = dict(record, session_id=str(uuid.uuid4()))
                recovery['write_json'](record_path, changed)
                press(b'p')
                wait(lambda: b'conversation changed' in output.lower())
                assert all(not path.read_bytes() for _,_,path in agents.values())
                recovery['write_json'](record_path, record)
            # Explicit prepare goes only to Codex, bracketed and without Enter.
            press(b'p')
            wait(lambda: active() == agents['codex'][0] and bool(agents['codex'][2].read_bytes()))
            pasted = agents['codex'][2].read_bytes()
            assert pasted.startswith(b'\x1b[200~') and pasted.endswith(b'\x1b[201~'), pasted
            assert b'\r' not in pasted and b'\n' not in pasted
            assert shlex.quote(context['feedback']).encode() in pasted
            assert not agents['claude'][2].read_bytes()
            assert not run('list-buffers', '-F', '#{buffer_name}')
            # Saved comments reopen, including at narrow SSH terminal sizes.
            fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack('HHHH',24,70,0,0))
            os.kill(client.pid, signal.SIGWINCH)
            wait(lambda: run('list-clients', '-F', '#{client_width}') == '70')
            open_review(agents['codex'][0])
            reopened = json.loads(finish().read_text())
            assert 'CODEX RANGE' in Path(reopened['feedback']).read_text()
            press(b'q');drain(0.15)
            # Moved lines create a fresh review store; earlier anchors stay archived.
            file.write_text('# shifted lines\n' + file.read_text())
            open_review(agents['codex'][0])
            with patch.dict(os.environ, env, clear=True):
                changed_revision = review['revision'](str(project))
                epoch = context_file.parent / 'revisions' / changed_revision['fingerprint']
                sessions = subprocess.run([args.tuicr, 'review', 'list', '--all'],
                                          env=review['review_environment'](epoch),
                                          capture_output=True, text=True, check=True)
                saved = json.loads(sessions.stdout)
                assert all(item.get('comment_count', 0) == 0 for item in saved), saved
                try:review['prepare'](run, client_name, dict(context, conversation=None))
                except ValueError as error:assert 'No exact conversation ID' in str(error)
                else:raise AssertionError('Missing conversation ID accepted')
            assert Path(context['feedback']).read_text() == markdown
            press(b':q\r');drain(0.2)
            # Local data/config/persistence never land in the checkout.
            assert git('status','--porcelain') == 'M demo.py'
            for path in (home / '.local/state/dotfiles/reviews').glob('*/*'):
                if path.suffix in ('.md','.json'):
                    assert path.stat().st_mode & 0o777 == 0o600
            assert run('list-panes', '-a', '-F', '#{pane_id}:#{pane_pid}') == original
            assert not list(root.rglob('injected'))
            print(json.dumps({'checks':'passed','real_tuicr':subprocess.check_output([args.tuicr,'--version'],text=True).strip(),
                              'review_first_paint_ms':round(popup_ms,1),'revision_check_ms':round(revision_ms,1),
                              'terminal_sizes':['120x40','70x24'],'fragmented_readiness_markers':sum(fragmented_markers),'idle_review_cpu_percent_sample':idle_percent,'fake_agents_only':True},indent=2))
        finally:
            subprocess.run(command + ['kill-server'], env=env, capture_output=True, timeout=5)
            if client is not None:
                try:client.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    client.kill()
                    client.wait(timeout=2)
            if master is not None:os.close(master)


if __name__ == '__main__':main()
