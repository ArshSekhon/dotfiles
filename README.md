# Personal development environment

Small chezmoi-managed configurations for agent development, with Ubuntu as the
first verified platform. [AGENTS.md](AGENTS.md) records scope and decisions;
[BOOTSTRAP.md](BOOTSTRAP.md) describes agent-run installation and preservation.
Package installation and configuration application are separate operations.

The `home/` source currently manages tmux, its workspace/scratch/recovery/task helpers,
zsh, Neovim, local tuicr reviews, and Claude's status-line renderer. Other platforms
still need testing.

## Agent status lines

Codex uses its native footer: model/reasoning, context remaining, branch and Fast
mode. Personal mode also includes five-hour and weekly subscription headroom.
`/statusline` selects/reorders native fields and has a Use theme colors toggle for
the active `/theme`; setup preserves your theme. Config changes apply to new sessions.
The footer remains separate from tmux's task names and attention indicators.

Claude's small `claude-statusline` command reads the native session JSON. It shows
model/effort, context remaining, optional Fast/Vim modes and branch; personal mode
adds five-hour/weekly headroom and local reset times when supplied. Percentages
are **remaining**, not consumed. Missing context is `?`; absent quotas stay hidden.
Reset times use the process timezone (`TZ` or the host default). At narrower widths,
branch is omitted when necessary and quotas use a second row; below 50 columns,
reset times are omitted. Tokyo Night colors need no special font; `NO_COLOR=1`
disables them. Colors warn at 20%/10% remaining capacity, not a model-quality cutoff.

Rendering uses POSIX sh, jq and a Git symbolic-HEAD lookup in the supplied folder,
without scanning changed files. No transcript/credential reads, usage API requests,
updates, installs, cache files or periodic refresh are configured. Setup needs
Python 3.11+ for standard-library TOML validation; it runs only on demand.

After applying the renderer, choose the machine context explicitly:

```sh
python3 scripts/setup-agent-statusline.py --mode personal --dry-run
python3 scripts/setup-agent-statusline.py --mode personal
# On a work machine, use --mode work for both commands.
```

Setup merges only Codex's `tui.status_line` and Claude's `statusLine`, preserving
attention/recovery hooks and other settings. The machine choice lives privately in
`$XDG_CONFIG_HOME/dotfiles/agent-statusline-mode` (default ~/.config/dotfiles/).
Agent configs remain unmanaged private files; never add whole configs to Git.
Claude reloads its setting automatically; existing Codex conversations keep running
and adopt the footer on their next launch. See [BOOTSTRAP.md](BOOTSTRAP.md#agent-status-line-setup)
for scoped application, backup/restoration and verification.

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
for that invocation. Neovim's native review/editing setup is described below.
[bat](https://github.com/sharkdp/bat), [fd](https://github.com/sharkdp/fd),
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

## Neovim

`v file` or `nvim file` opens the native review/editing setup: absolute line numbers,
current-line highlighting, a compact filename/position status line, and the built-in
dark habamax theme. Search ignores case until you type capitals; substitutions
preview their changes. Native filetype support and
[EditorConfig](https://neovim.io/doc/user/editorconfig/) control project indentation,
with four spaces as the fallback. No downloads or updates run in the editor.

Native LSP connects Java (JDT LS), JS/TS/JSX/TSX (typescript-language-server), Rust
(rust-analyzer), Python (Pyright), HTML, and Markdown (Marksman). Mermaid files and
Markdown fences use built-in syntax highlighting. Servers start for matching files
and reuse clients per project; large files skip LSP. Java and Rust use offline
analysis defaults with automatic builds disabled. Fetch project dependencies outside
the editor; private overrides can enable heavier analysis when needed.

[fzf-lua](https://github.com/ibhagwan/fzf-lua), [Flash](https://github.com/folke/flash.nvim),
[Gitsigns](https://github.com/lewis6991/gitsigns.nvim), and
[Conform](https://github.com/stevearc/conform.nvim) load on their shortcuts. They provide
fuzzy discovery, labeled jumps, changed-hunk navigation, and manual formatting.
Native packages are installed separately; startup never fetches plugins.

| Key / command | Action |
| --- | --- |
| Space, w / Space, q | Save / close the current window; unsaved edits require a decision |
| Space, e | Browse files with native netrw; Enter opens, `-` goes to the parent |
| Ctrl+p / Space, ff | Find project files; Ctrl+j/k moves, Enter opens, Esc cancels |
| Space, fg / fb / fr | Search project text / open buffers / recent files |
| Space, fs / fS | File / workspace symbols through LSP |
| Space, j | Flash jump: type a target, then its label |
| Space, fo | Start `:edit`; Tab completes file paths |
| Space, / | Search from the current directory with ripgrep; results open in quickfix |
| `:cnext` / `:cprev` / `:cclose` | Next / previous search result / close the results window |
| Ctrl+h/j/k/l | Move between editor splits |
| `:vsplit file` / `:split file` | Open a file beside / below the current window |
| Space, y | Copy the current line, a count of lines, or a visual selection to the device clipboard |
| Esc | Clear search highlighting in normal mode |
| Space, ? / vc / vl | Cheatsheet / installed config / language settings |
| `gd` / `K` / `grr` | Definition / hover / references; Ctrl+O returns |
| `grn` / `gra` / Space, d | Rename / code action / line diagnostics |
| Ctrl+Space (insert mode) | Request completion; Ctrl+n/p selects, Ctrl+y accepts |
| Space, lt | Toggle language services; turn off for a plain review to release their resources |
| Space, = | Format file/selection: Prettier for web/Markdown, Ruff for Python, rustfmt for Rust, JDT for Java |
| Space, gf / gg / gh | Changed files / enable Git signs and hunk keys / preview hunk |
| `]c` / `[c` | Next / previous changed hunk after Git signs attach |
| `nvim -d old new` | Native side-by-side diff; `]c` / `[c` moves between changes |

Over SSH, Space, y uses native OSC 52 on demand. Paste with the terminal's normal
shortcut. Its escape sequences are verified in isolated terminals; delivery to
Ghostty/RootShell still needs a local paste check. Other local terminals use Neovim's
native clipboard provider. The SSH shortcut needs native OSC 52/getregion support;
the Ubuntu pilot uses Neovim 0.12.5.

[Persistent undo](https://neovim.io/doc/user/undo/#undo-persistence) lives in a private
`stdpath('state')/undo` directory, outside checkouts. Native swap/crash recovery stays
enabled. Returning to a buffer checks for external changes; `:checktime` checks
manually. No background file watcher is added. Private overrides go in the unmanaged
`~/.config/nvim/init.local.lua` (or `$XDG_CONFIG_HOME/nvim/init.local.lua`), loaded last.
Space, ? describes server settings and limitations. Space, vc/vl opens installed
configuration for inspection; edit `home/dot_config/nvim/` in this repository to
keep managed changes. Formatting runs explicitly, without changing save behavior.
Mermaid rendering is a separate tool; this setup edits/highlights diagram source.

Preview/apply just the editor configuration:

```sh
chezmoi --source="$PWD" --no-pager diff --recursive ~/.config/nvim
chezmoi --source="$PWD" apply --dry-run --recursive --parent-dirs ~/.config/nvim
# After reviewing the preview and preserving existing settings:
chezmoi --source="$PWD" apply --recursive --parent-dirs ~/.config/nvim
nvim --headless -u NONE -c 'helptags ~/.config/nvim/doc' -c qa
```

## Existing tmux work

Ctrl+A, ? opens the shortcut cheatsheet: j/k scrolls, / searches, and q closes.

Ctrl+A, **s** opens the session picker with stable letter shortcuts instead of
numbered rows. Press a displayed letter to jump, or j/k (Up/Down) then Enter.
**e** edits the selected session's shortcut; Backspace clears it and Esc cancels.
**j/k** selects down/up; **J/K** moves the selected session down/up in this list
(Shift+Down/Up also works). e/j/k/q/J/K are reserved for these controls.
**Ctrl+L** refreshes and Esc/q closes. Keys are case-sensitive and
initially chosen from session names. Order and keys persist by name in private
`$XDG_STATE_HOME/dotfiles/sessions/preferences.json` (default under
`~/.local/state/`), including reopened/restored sessions with the same name.
This order applies to this picker; tmux's native IDs and other pickers retain
their own order. Ctrl+A, w continues to open the native window tree.
Earlier shortcuts using e/J/K automatically receive another available letter;
session order and other shortcuts stay saved.

Ctrl+A, **Shift+Arrow** swaps the active pane with its neighbor in that direction,
keeping focus on the same running process. At an outer edge it stays put; a zoomed
pane reveals its layout before moving. h/j/k/l selects panes and H/J/K/L resizes
them. Pane labels, agent IDs and attention stay with the pane. These keys move
panes within the current window; they do not move them between sessions.

For quick back-and-forth, **Ctrl+A, b** returns to the last session,
**Ctrl+A, Tab** to the last window, and **Ctrl+A, p** to the last pane in the
current window (keeping zoom). Press the same shortcut again to return.
**Ctrl+A, Shift+B** toggles the last two task panes visited through the task switcher.

Ctrl+A, g searches sessions, windows, pane labels, tools, and folders. Enter jumps;
Alt+s opens a shell in the selected folder, and Ctrl+R opens its local review.
Ctrl+A, Shift+B returns to the previous task. Workspace (Ctrl+A, Shift+N) also has
a g shortcut. See [AGENTS.md](AGENTS.md) for labels, hiding, and picker controls.
The picker reads tmux metadata on demand. Managed Codex/Claude invocations report
attention through native hooks into a shared event reducer; there is no watcher,
daemon, transcript inspection or idle polling. See [bootstrap setup and signal
limits](BOOTSTRAP.md#agent-attention-setup-and-event-contract).

Ctrl+A, **a** jumps to the next agent needing attention; Ctrl+A, **Shift+A** opens
the attention queue. It includes hidden panes, prioritizes pending input, then
errors, then unread responses, and counts linked windows only once. In the task
picker, **Alt+u** toggles attention only; **Alt+m** marks the selected alert seen.
The bottom status line shows input/error/ready counts (compact `!`/`E`/`+` on narrow
terminals); window markers and named-pane captions show the reported state.

Visiting through these pickers acknowledges a response/error. Pending input stays
pending until its adapter reports resolution; a visit or mark-seen never answers it.
Ordinary pane movement does not acknowledge alerts. Ready means a response was
reported, and can precede continuation; it does not mean the task is complete.
Existing live panes stay untouched and show unavailable status until a new managed
invocation. For Codex, review/trust the new commands with `/hooks` in a new session.

### Nested tmux

Use **Ctrl+A for outer tmux** and **Ctrl+B for a separate inner/remote server**.
On the inner host, apply the managed `~/.config/tmux/inner.conf` profile and add
this line at the end of its private `~/.tmux.local.conf`:

```tmux
source-file ~/.config/tmux/inner.conf
```

Run `tmux source-file ~/.config/tmux/inner.conf` there to activate it immediately,
without restarting sessions or reloading plugins. Ctrl+A, s opens outer sessions;
Ctrl+B, s opens inner sessions. All documented Ctrl+A shortcuts use Ctrl+B on
that inner server, and Ctrl+B twice sends a literal Ctrl+B to its application.
The choice is explicit per server, including when connected directly; SSH does
not change it automatically. See [setup and restoration](BOOTSTRAP.md#nested-tmux-checks).

Enable `mouse on` in both layers. Native tmux wheel bindings forward events when
the inner tmux requests mouse input; an inner layer with mouse disabled can make
the outer layer enter copy mode instead. Check the effective settings and custom
bindings with the [nested-session diagnostic recipe](BOOTSTRAP.md#nested-tmux-checks).

If both layers still use Ctrl+A, press **Ctrl+A, Ctrl+A, then the key** to control the
inner layer: for example, Ctrl+A, Ctrl+A, [ opens its copy mode, and Ctrl+A,
Ctrl+A, d detaches the inner client. Ctrl+A, [ still opens the outer copy mode.
For longer remote work, a dedicated terminal tab connected directly to the remote
tmux keeps one layer of shortcuts and scrollback.

### SSH clipboard

Copy text to the connected device: **Ctrl+A, [** enters copy mode, **v** starts
selection, **h/j/k/l** moves, and **y** copies and exits. Paste in a local app.
From a shell inside tmux, copy a file or command output:

```sh
tmux load-buffer -w path/to/file
git diff | tmux load-buffer -w -
```

The managed configuration uses native OSC 52 over SSH, with no clipboard daemon.
[Ghostty](https://ghostty.org/docs/config/reference#clipboard-write) allows writes by
default; [RootShell](https://www.rootshell.com/release-notes.html) also supports OSC 52
(control-mode pane support was added in 1.0.8-108). Verify each device by copying a
known marker and pasting into a local note; a tmux buffer alone does not prove delivery.

## Local reviews

Ctrl+A, r reviews the current checkout; Ctrl+A, g then Ctrl+R reviews the
selected task. [Tuicr](https://github.com/agavra/tuicr) uses `c`/`C` for line/file
comments, `v` then `c` for a range, and Enter to save. `ZZ` exports privately;
`p` pastes a feedback prompt in that agent's pane, where Enter sends it.
Clear any existing agent draft before preparing. `v` views the
saved feedback, `r` reviews again, and `q` closes. No SSH clipboard is required.

Preparation checks the exact conversation ID and Git revision. Existing unmanaged
conversations need explicit binding as described in BOOTSTRAP.md. Reopening unchanged
code keeps comments; changed revisions start fresh while earlier feedback stays saved.
Reviews stay under ~/.local/state/dotfiles/reviews/, outside project checkouts.
The private wrapper currently supports Linux; macOS isolation is pending its rollout.

Shortcut definitions live in `home/dot_local/bin/tmux_keys.py`. After editing,
run `python3 scripts/sync-tmux-keys.py`; CI and `--check` reject a stale cheatsheet
or native binding block. Popup actions/hints read that same catalog. Apply the
catalog, affected helpers, tmux configuration, and cheatsheet together.
Use `?` inside tuicr for its own version's complete controls.

## Verification

```sh
python3 scripts/inspect-machine.py --json
zsh -n home/dot_zshenv
zsh -n home/dot_zshrc
python3 scripts/verify-tmux.py
python3 scripts/verify-sessions.py
python3 scripts/verify-tasks.py
python3 scripts/verify-reviews.py
python3 scripts/sync-tmux-keys.py --check
```

Follow the short shell verification recipe in [BOOTSTRAP.md](BOOTSTRAP.md).
Use isolated homes/state for behavior and chezmoi checks, and record performance
measurements privately. The tmux verifier covers the custom workspace helpers.

The tmux controls, scratch tasks, and launcher are documented in
[AGENTS.md](AGENTS.md). Exact-ID recovery setup and verification are in
[BOOTSTRAP.md](BOOTSTRAP.md#agent-recovery-setup).
