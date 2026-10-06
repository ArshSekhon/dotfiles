# Personal development environment

Small chezmoi-managed configurations for agent development, with Ubuntu as the
first verified platform. [AGENTS.md](AGENTS.md) records scope and decisions;
[BOOTSTRAP.md](BOOTSTRAP.md) describes agent-run installation and preservation.
Package installation and configuration application are separate operations.

The `home/` source currently manages tmux, its workspace/scratch/recovery helpers, a zsh
environment, and a tuicr trial configuration. Other platforms still need testing.

## Zsh

Start with `zsh` after bootstrap. Changing the login shell or the shell used by
new tmux panes is a separate explicit choice; applying these files does neither.
The Ubuntu pilot now uses zsh for login and newly created tmux shells. Existing
panes keep their current processes. Its shell choice is a private tmux override.

- Native Vim editing, a 10 ms Escape timeout, and Up/Down history prefix search.
- Shared history across panes, capped at 10,000 saved entries, in
  `$XDG_STATE_HOME/zsh/history` (default `~/.local/state/zsh/history`). A leading
  space excludes a command from history; this is not automatic secret detection.
- Native menu completion with case-insensitive fallback and permission checks.
- A compact hostname, directory, branch/action, and failed-command-status prompt.
  Branch information refreshes at prompts; it does not scan changed files.
- [zsh-autosuggestions](https://github.com/zsh-users/zsh-autosuggestions) uses
  asynchronous history suggestions, capped for long command buffers.
  [zsh-syntax-highlighting](https://github.com/zsh-users/zsh-syntax-highlighting)
  highlights commands as you type and skips very long buffers.
- [fzf](https://github.com/junegunn/fzf) supplies Ctrl+R history search, Ctrl+T
  file insertion, Alt+C directory selection, and `**` + Tab fuzzy completion.
  File/directory shortcuts use fd/fdfind when installed, respect ignore files,
  and exclude common dependency/build directories. Searches run on demand.
- `gs`, `gd`, `gds`, and `gw` show Git status, unstaged diff, staged diff, and
  worktree locations. `v` in normal mode or Ctrl+X Ctrl+E edits the current
  command in `$VISUAL`/`$EDITOR`, defaulting to Neovim when available.

The CLI essentials are chosen for finding files, moving between tasks, reading
changes, and small edits:

| Command | Use |
| --- | --- |
| `cat file` / `bat file` | bat syntax highlighting; the `cat` alias uses plain styling and never opens a pager |
| `fd pattern` / `rg -n pattern` | Find filenames / search contents; respect project ignore files |
| `z project` / `zi` | zoxide learns visited directories; jump by name / select with fzf |
| `..` / `...` | Go up one / two directories |
| `v file` / `vim file` / `nvim file` | Open Neovim |
| `gdp` / `gdp --staged` | Use delta for this Git diff, with line numbers and file navigation |
| `jq . file.json` / `htop` | Inspect JSON / diagnose process CPU and memory; already installed on the pilot |

Aliases apply to interactive zsh. Use `command cat` for the system command when
you need its exact options. Plain `gd` remains available; `gdp` sets its pager
for that invocation. Neovim uses native defaults; an editor plugin setup is future
work. [bat](https://github.com/sharkdp/bat), [fd](https://github.com/sharkdp/fd),
[ripgrep](https://github.com/BurntSushi/ripgrep),
[zoxide](https://github.com/ajeetdsouza/zoxide), and
[delta](https://github.com/dandavison/delta) are installed separately from config.

Private changes go in `~/.zshrc.local` (or `$ZDOTDIR/.zshrc.local`), outside Git.
It loads before the plugins, so local widgets are included in highlighting.
For Ctrl-style editing, put `bindkey -e` there. Preserve local runtime, employer,
and credential settings instead of copying Bash startup files into zsh.
Autosuggestions bind widgets once. If you define additional widgets later in a
running shell, run `_zsh_autosuggest_bind_widgets` to include them.

Startup runs no installs, updates, or network requests. `~/.local/bin` is added
to PATH. Existing mise shims are added for interactive/login shells using native
PATH operations, without activation hooks. Non-interactive commands inherit the
resolved runtime PATH. Shims select project runtimes per command but incur dispatch
cost and do not apply mise environment variables to the parent shell; use
[`mise exec -- <command>`](https://mise.jdx.dev/dev-tools/shims.html) for explicit
project environments and groups of runtime calls.

Bootstrap installs the current stable zsh separately, resolves stable upstream
plugin tags, and places plugin checkouts under `$XDG_DATA_HOME/zsh/plugins/`
(default `~/.local/share/zsh/plugins/`). Generate the installed fzf's integration
once with `fzf --zsh` into `$XDG_DATA_HOME/zsh/fzf.zsh`. Plugin and integration
files are installation artifacts, not managed configuration. Rebuild that file
when deliberately upgrading fzf. Missing plugins leave native features usable.
Record versions/sources and back up conflicts privately as specified in BOOTSTRAP.
Generate `zoxide init zsh --hook pwd` once into `$XDG_DATA_HOME/zsh/zoxide.zsh`;
regenerate it when upgrading zoxide. It records directory changes, with no work
at idle prompts. Its private database lives in `$XDG_DATA_HOME/zoxide` by default;
override `_ZO_DATA_DIR` privately if needed. Install upstream zsh completions in
`$XDG_DATA_HOME/zsh/site-functions/`. Upgrades are deliberate; startup only reads
these installed assets.

Preview only the requested shell files before applying them:

```sh
chezmoi --source="$PWD" --no-pager diff ~/.zshenv ~/.zshrc
chezmoi --source="$PWD" apply --dry-run ~/.zshenv ~/.zshrc
```

## Local reviews

[Tuicr](https://github.com/agavra/tuicr) supports local line/range comments and
review export. Once installed, `tuicr -w` or Ctrl+A, r opens the review;
`c` adds a comment and `ZZ` exports and exits. Comments/progress stay outside Git.
Use `gdp` for quick diff reading and tuicr for reviews with feedback.

The Ubuntu pilot has verified a temporary tuicr 0.27.0 binary. It has no persistent
tuicr command on PATH, and the managed configuration is not applied yet.
SSH clipboard, moved-line comment anchors, and real-terminal performance checks
remain before rollout; see [AGENTS.md](AGENTS.md) for the trial results.

## Verification

```sh
python3 scripts/inspect-machine.py --json
zsh -n home/dot_zshenv
zsh -n home/dot_zshrc
python3 scripts/verify-tmux.py
```

Follow the short shell verification recipe in [BOOTSTRAP.md](BOOTSTRAP.md).
Use isolated homes/state for behavior and chezmoi checks, and record performance
measurements privately. The tmux verifier covers the custom workspace helpers.

The tmux controls, scratch tasks, and launcher are documented in
[AGENTS.md](AGENTS.md). Exact-ID recovery setup and verification are in
[BOOTSTRAP.md](BOOTSTRAP.md#agent-recovery-setup); feedback handoff remains planned.
