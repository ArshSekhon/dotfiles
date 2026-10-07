#!/usr/bin/env python3
"""Generate static tmux bindings/help from the catalog; --check rejects drift."""
import argparse
from pathlib import Path
import runpy
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='check without writing')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    keys = runpy.run_path(str(root / 'home/dot_local/bin/tmux_keys.py'))
    config = root / 'home/dot_tmux.conf'
    before, marker, after = config.read_text().partition('# BEGIN GENERATED KEYS\n')
    old, end, tail = after.partition('# END GENERATED KEYS\n')
    if not marker or not end:
        raise ValueError('Missing generated binding markers')
    if any(line.startswith(('bind ', 'bind-key ')) for line in (before + tail).splitlines()):
        raise ValueError('Put shared bindings in tmux_keys.py, not outside the generated block')
    targets = {config: before + marker + keys['native_bindings']() + end + tail,
               root / 'home/dot_config/tmux/cheatsheet.txt': keys['cheatsheet']()}
    stale = [path for path, expected in targets.items() if not path.exists() or path.read_text() != expected]
    if args.check:
        if stale:
            for path in stale:
                print('Stale: ' + str(path.relative_to(root)), file=sys.stderr)
            raise SystemExit('Run python3 scripts/sync-tmux-keys.py and apply the changed files together.')
        print('Tmux bindings and cheatsheet are in sync.')
    else:
        for path in stale:
            path.write_text(targets[path])
            print('Updated ' + str(path.relative_to(root)))


if __name__ == '__main__':
    main()
