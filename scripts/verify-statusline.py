#!/usr/bin/env python3
"""Check our renderer and additive settings merge with disposable JSON/Git homes.

Requires Python 3.11+, jq and Git. No real agents, sessions, credentials or network.
"""

import copy
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import tomllib


def main():
    repo = Path(__file__).resolve().parents[1]
    setup = runpy.run_path(str(repo / 'scripts/setup-agent-statusline.py'))
    source = repo / 'home/dot_local/bin/executable_claude-statusline'
    if not shutil.which('jq') or not shutil.which('git'):
        raise SystemExit('jq and Git are required.')
    with tempfile.TemporaryDirectory(prefix='dotfiles-statusline-') as temporary:
        root = Path(temporary)
        home = root / "home ' quoted"
        helper = home / '.local/bin/claude-statusline'
        helper.parent.mkdir(parents=True)
        shutil.copyfile(source, helper)
        helper.chmod(0o700)
        env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / '.config'),
                   XDG_STATE_HOME=str(home / '.local/state'),
                   CODEX_HOME=str(home / '.codex'), CLAUDE_CONFIG_DIR=str(home / '.claude'),
                   NO_COLOR='1', TZ='UTC', COLUMNS='120')
        for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE'):
            env.pop(key, None)
        folder = root / 'different checkout'
        folder.mkdir()
        subprocess.run(['git', 'init', '-q', '-b', 'fixture-branch', str(folder)], env=env, check=True)
        mode_path = home / '.config/dotfiles/agent-statusline-mode'
        fixture = {'model': {'display_name': 'Claude'}, 'effort': {'level': 'high'},
                   'workspace': {'current_dir': str(folder)},
                   'context_window': {'remaining_percentage': 63},
                   'rate_limits': {'five_hour': {'used_percentage': 58, 'resets_at': 1791414000},
                                   'seven_day': {'used_percentage': 22, 'resets_at': 1791658800}}}

        def render(data, width=120, **extra):
            result = subprocess.run(['/bin/sh', str(helper)], env=dict(env, COLUMNS=str(width), **extra),
                                    input=json.dumps(data), text=True, capture_output=True, check=True, timeout=5)
            assert not result.stderr, result.stderr
            return result.stdout.rstrip('\n')

        assert render(fixture) == 'Claude high | ctx 63% left | fixture-branch'
        assert render({}) == 'Claude | ctx ?'
        assert render({'context_window': {'remaining_percentage': None}}) == 'Claude | ctx ?'
        assert render({'context_window': {'remaining_percentage': 0, 'used_percentage': 0}}) == 'Claude | ctx 0% left'
        assert render({'context_window': {'remaining_percentage': 0}}) == 'Claude | ctx 0% left'
        assert render({'context_window': {'used_percentage': 8}}) == 'Claude | ctx 92% left'
        assert 'fast NORMAL' in render({'fast_mode': True, 'vim': {'mode': 'NORMAL'}})
        colored = render(fixture, NO_COLOR='')
        assert '\x1b[38;2;122;162;247m' in colored
        assert re.sub(r'\x1b\[[0-9;]*m', '', colored) == render(fixture)
        for remaining, rgb in ((19, '224;175;104'), (9, '247;118;142')):
            assert '\x1b[38;2;' + rgb + 'm' in render({'context_window': {'remaining_percentage': remaining}}, NO_COLOR='')

        # TOML comments/unknown/private settings survive; only one array may change.
        items = setup['native_items']('personal')
        samples = [
            '', '# private comment\nmodel = "fixture"\n',
            '[tui]\nnotifications = false\n[tui.model_availability_nux]\nfixture = 4\n',
            '[tui]\nstatus_line = [\n  "model", # retain other comments\n  "context-used",\n]\nnotifications = true\n',
            'tui.status_line = ["model"]\ntui.animations = false\n[other]\nsecret = "retained"\n',
            'tui.animations = false\n',
        ]
        for text in samples:
            after = setup['merge_codex'](text, items)
            expected = tomllib.loads(text)
            expected.setdefault('tui', {})['status_line'] = items
            assert tomllib.loads(after) == expected
            assert setup['merge_codex'](after, items) == after
        for text in ('tui = { animations = false }\n', '["tui"]\nanimations = true\n',
                     'tui = false\n', 'invalid TOML ['):
            try:
                setup['merge_codex'](text, items)
            except ValueError:
                pass
            else:
                raise AssertionError('Unsupported TOML must fail without replacing unrelated settings.')

        codex = home / '.codex/config.toml'
        claude = home / '.claude/settings.json'
        codex.parent.mkdir()
        claude.parent.mkdir()
        codex.write_text('# private\nmodel = "fixture"\n[tui]\nanimations = false\n')
        settings = {'hooks': {'SessionStart': [{'hooks': [{'type': 'command', 'command': 'fixture-only'}]}]},
                    'permissions': {'allow': ['fixture']}, 'custom': {'keep': True}}
        claude.write_text(json.dumps(settings))
        codex.chmod(0o640)
        originals = {path: path.read_bytes() for path in (codex, claude)}
        command = [sys.executable, str(repo / 'scripts/setup-agent-statusline.py'), '--mode', 'personal']
        preview = subprocess.run(command + ['--dry-run'], env=env, text=True, capture_output=True, check=True)
        assert 'Would update:' in preview.stdout and not mode_path.exists()
        assert all(path.read_bytes() == data for path, data in originals.items())
        assert not (home / '.local/state').exists()
        subprocess.run(command, env=env, capture_output=True, check=True)
        updated = json.loads(claude.read_text())
        assert {k: v for k, v in updated.items() if k != 'statusLine'} == settings
        assert updated['statusLine']['type'] == 'command' and 'refreshInterval' not in updated['statusLine']
        assert codex.stat().st_mode & 0o777 == 0o640
        assert mode_path.stat().st_mode & 0o777 == 0o600
        snapshot = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (codex, claude, mode_path)}
        rerun = subprocess.run(command, env=env, text=True, capture_output=True, check=True)
        assert 'Already configured' in rerun.stdout
        assert all((p.read_bytes(), p.stat().st_mtime_ns) == saved for p, saved in snapshot.items())
        # Execute the exact quoted command configured for a HOME containing quotes.
        assert subprocess.run(updated['statusLine']['command'], shell=True, env=env, input=json.dumps(fixture),
                              text=True, capture_output=True, check=True).stdout == render(fixture) + '\n'
        assert '5h 42% left @' in render(fixture) and 'wk 78% left @' in render(fixture)
        for width in (120, 70, 40, 24):
            for data in (fixture, {'model': {'display_name': '模型 ' * 20}, 'worktree': {'branch': '分支' * 20},
                                   'context_window': {'remaining_percentage': 0},
                                   'rate_limits': {'five_hour': {'used_percentage': 0}, 'seven_day': {'used_percentage': 0}}}):
                lines = render(data, width).splitlines()
                assert 1 <= len(lines) <= 2
                assert all(len(line.encode()) <= width for line in lines), lines
        malicious = {'model': {'display_name': 'Claude\x1b]52;c;fake\x07\n'}}
        assert '\x1b' not in render(malicious) and '\n' not in render(malicious)
        native = copy.deepcopy(fixture)
        native['worktree'] = {'branch': 'native-worktree'}
        assert 'native-worktree' in render(native) and 'fixture-branch' not in render(native)
        assert render({'rate_limits': {'five_hour': {'used_percentage': 0}}}).endswith('5h 100% left')
        assert 'wk 0% left' in render({'rate_limits': {'seven_day': {'used_percentage': 120}}})
        assert '5h' not in render({'rate_limits': {'five_hour': {'used_percentage': None}}})

        # Malformed/symlink targets refuse the whole setup before any writes.
        saved_claude = claude.read_bytes()
        claude.write_text('invalid JSON')
        result = subprocess.run(command, env=env, capture_output=True)
        assert result.returncode != 0 and codex.read_bytes() == snapshot[codex][0]
        claude.write_bytes(saved_claude)
        codex.unlink()
        target = root / 'do-not-touch'
        target.write_bytes(originals[codex])
        codex.symlink_to(target)
        assert subprocess.run(command, env=env, capture_output=True).returncode != 0
        assert target.read_bytes() == originals[codex]
        codex.unlink()
        codex.write_bytes(snapshot[codex][0])

        # Switching work/personal removes recurring refresh and preserves hooks.
        updated['statusLine']['refreshInterval'] = 1
        claude.write_text(json.dumps(updated))
        subprocess.run(command[:-1] + ['work'], env=env, capture_output=True, check=True)
        assert mode_path.read_text() == 'work\n'
        assert 'five-hour-limit' not in tomllib.loads(codex.read_text())['tui']['status_line']
        assert '5h' not in render(fixture)
        assert json.loads(claude.read_text())['hooks'] == settings['hooks']
        assert 'refreshInterval' not in json.loads(claude.read_text())['statusLine']
        backups = sorted((home / '.local/state/dotfiles/backups').glob('agent-statusline-*'))
        assert len(backups) == 2
        for backup in backups:
            assert backup.stat().st_mode & 0o777 == 0o700
            for path in backup.iterdir():
                assert path.stat().st_mode & 0o777 == 0o600
        # Restore the first merge, identified by the previously absent mode file.
        first = next(b for b in backups if any(not e['existed'] for e in json.loads((b / 'manifest.json').read_text())))
        for entry in json.loads((first / 'manifest.json').read_text()):
            path = Path(entry['target'])
            if entry['existed']:
                path.write_bytes((first / entry['backup']).read_bytes())
                path.chmod(entry['mode'])
            else:
                path.unlink()
        assert all(path.read_bytes() == data for path, data in originals.items())
        assert not mode_path.exists() and codex.stat().st_mode & 0o777 == 0o640

        timings = []
        for _ in range(30):
            start = time.perf_counter()
            render(fixture)
            timings.append((time.perf_counter() - start) * 1000)
        print('PASS: JSON rendering, widths/colors, checkout identity, additive TOML/JSON, previews/reruns, private backups/restoration.')
        print('Synthetic work renderer with Git: {:.1f} ms median / {:.1f} ms max (30 warm invocations).'.format(
            statistics.median(timings), max(timings)))


if __name__ == '__main__':
    main()
