#!/usr/bin/env python3
"""Preview/merge native agent status lines; never replace whole agent configs.

Python 3.11+ is used only during setup for stdlib TOML validation. Claude rendering
uses POSIX sh, jq and optional Git. Agent settings and the machine mode stay private.
"""

import argparse
import copy
import json
import os
from pathlib import Path
import re
import shlex
import stat
import sys
import tempfile
import tomllib
import uuid


def native_items(mode):
    items = ['model-with-reasoning', 'context-remaining']
    if mode == 'personal':
        items.extend(['five-hour-limit', 'weekly-limit'])
    return items + ['git-branch', 'fast-mode']


def merge_codex(text, items):
    """Keep comments/private keys verbatim; validate that only our array changes.

    Handle ordinary [tui] tables and root dotted keys. Unusual inline/quoted table
    forms fail without writing; do not invent a whole-file TOML serializer.
    """
    before = tomllib.loads(text)
    expected = copy.deepcopy(before)
    tui = expected.setdefault('tui', {})
    if not isinstance(tui, dict):
        raise ValueError('Codex tui must be a table.')
    if tui.get('status_line') == items:
        return text
    tui['status_line'] = items
    lines = text.splitlines(keepends=True)
    assignment = 'status_line = ' + json.dumps(items) + '\n'
    header = re.compile(r'^\s*\[tui\]\s*(?:#.*)?$')
    table = re.compile(r'^\s*\[')
    key = re.compile(r'^\s*(?:status_line|"status_line"|\'status_line\')\s*=')
    dotted = re.compile(r'^\s*tui\s*\.\s*status_line\s*=')
    begin = next((i for i, line in enumerate(lines) if header.match(line)), None)
    start = 0 if begin is None else begin + 1
    stop = next((i for i in range(start, len(lines)) if table.match(lines[i])), len(lines))
    match = next((i for i in range(start, stop) if (dotted if begin is None else key).match(lines[i])), None)
    if match is not None:
        replacement = ('tui.' if begin is None else '') + assignment
        # Multiline arrays may contain comments and brackets inside strings.
        # Parsed equality proves the replacement cannot swallow another setting.
        for end in range(match + 1, stop + 1):
            candidate = ''.join(lines[:match]) + replacement + ''.join(lines[end:])
            try:
                if tomllib.loads(candidate) == expected:
                    return candidate
            except tomllib.TOMLDecodeError:
                pass
    else:
        if begin is not None:
            candidate = ''.join(lines[:start]) + assignment + ''.join(lines[start:])
        elif 'tui' in before:
            candidate = 'tui.' + assignment + text
        else:
            candidate = text + ('\n' if text and not text.endswith('\n') else '') + '\n[tui]\n' + assignment
        try:
            if tomllib.loads(candidate) == expected:
                return candidate
        except tomllib.TOMLDecodeError:
            pass
    raise ValueError('Unsupported Codex tui layout; merge tui.status_line manually. No files changed.')


def absolute_directory(env_key, fallback):
    path = Path(os.environ.get(env_key, str(fallback))).expanduser()
    if not path.is_absolute():
        raise ValueError(env_key + ' must be absolute.')
    return path


def original(path):
    if path.is_symlink():
        raise ValueError('Refusing a symlink configuration target: ' + str(path))
    if not path.exists():
        return None, 0o600
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > 2 * 1024 * 1024:
        raise ValueError('Configuration must be an owned regular file under 2 MiB: ' + str(path))
    return path.read_bytes(), stat.S_IMODE(info.st_mode)


def write_atomic(path, content, mode):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix='.statusline-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def setup(mode, dry_run, renderer):
    home = Path.home()
    config = absolute_directory('XDG_CONFIG_HOME', home / '.config')
    state = absolute_directory('XDG_STATE_HOME', home / '.local/state')
    codex = absolute_directory('CODEX_HOME', home / '.codex') / 'config.toml'
    claude = absolute_directory('CLAUDE_CONFIG_DIR', home / '.claude') / 'settings.json'
    renderer = Path(renderer).expanduser() if renderer else home / '.local/bin/claude-statusline'
    if not renderer.is_absolute() or not renderer.is_file() or not os.access(renderer, os.X_OK):
        raise ValueError('Apply the executable claude-statusline helper first.')
    mode_path = config / 'dotfiles/agent-statusline-mode'
    paths = (codex, claude, mode_path)
    if len(set(path.resolve() for path in paths)) != len(paths):
        raise ValueError('Configuration targets must be distinct.')
    saved = {path: original(path) for path in paths}
    codex_bytes = merge_codex((saved[codex][0] or b'').decode('utf-8'), native_items(mode)).encode('utf-8')
    data = json.loads(saved[claude][0] or b'{}')
    if not isinstance(data, dict):
        raise ValueError('Claude settings must be an object.')
    # Replace this single setting; retain hooks, permissions, models and all others.
    data['statusLine'] = {'type': 'command', 'command': shlex.quote(str(renderer)), 'padding': 0}
    claude_bytes = (json.dumps(data, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
    if saved[claude][0] is not None and json.loads(saved[claude][0]) == data:
        claude_bytes = saved[claude][0]  # Reruns do not normalize unrelated whitespace.
    desired = {codex: codex_bytes, claude: claude_bytes, mode_path: (mode + '\n').encode()}
    changed = [path for path in paths if saved[path][0] != desired[path]]
    print('Mode: ' + mode + '; Codex: ' + ', '.join(native_items(mode)))
    for path in changed:
        print(('Would update: ' if dry_run else 'Update: ') + str(path))
    if not changed:
        print('Already configured; no files changed.')
        return
    if dry_run:
        return
    backup = state / 'dotfiles/backups' / ('agent-statusline-' + str(uuid.uuid4()))
    backup.mkdir(parents=True, mode=0o700)
    backup.chmod(0o700)
    manifest = []
    for index, path in enumerate(changed):
        content, permissions = saved[path]
        name = str(index) + '-' + path.name
        if content is not None:
            write_atomic(backup / name, content, 0o600)
        manifest.append({'target': str(path), 'existed': content is not None,
                         'mode': permissions, 'backup': name if content is not None else None})
    write_atomic(backup / 'manifest.json', (json.dumps(manifest, indent=2) + '\n').encode(), 0o600)
    # Recheck all snapshots before writing; other agents may edit private settings.
    if any(original(path) != saved[path] for path in paths):
        raise ValueError('Configuration changed during setup; rerun to preserve concurrent work.')
    for path in changed:
        write_atomic(path, desired[path], saved[path][1])
    print('Backup: ' + str(backup))
    print('Claude reloads settings; Codex uses the footer in new sessions. Existing panes keep running.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', required=True, choices=('work', 'personal'))
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--renderer', help='Installed renderer path (default: ~/.local/bin/claude-statusline)')
    args = parser.parse_args()
    setup(args.mode, args.dry_run, args.renderer)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, TypeError) as error:
        print('Agent status line: ' + str(error), file=sys.stderr)
        sys.exit(1)
