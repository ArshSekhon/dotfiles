# Dotfiles: vision, plan, and agent instructions

This file holds shared project context and working rules. Keep it concise and current.
CLAUDE.md imports it; scripts/ contains inventory and verification commands.
Read [BOOTSTRAP.md](BOOTSTRAP.md) for tool requirements and agent-run setup.
Inspect Git status before editing and preserve unrelated work. Work with the user
in small milestones. Keep user-facing updates and handoffs brief.

## Vision

A fast, understandable environment managed through chezmoi for development
primarily through Codex and Claude. Onboarding includes installing the latest
stable tools, initial configuration, preserving existing settings, and verification.
Performance is the first priority; software must also be reliable.

Priorities: shell speed, project/file discovery, remote clipboard, persistent
sessions, and responsive Neovim for reviewing changes and small manual edits.
Several agents commonly work on one project: make tasks, checkouts, and sessions
visible. Evaluate Git worktrees for independent edits; the workflow is still open.
Give ad-hoc drafting/research a named scratch workspace with private resources
outside project checkouts. Keep its files when the tmux window closes.

Agreed tmux direction: Ctrl+A prefix, compact bottom status line, named project/task
windows, agent discovery and attention shortcuts, and SSH clipboard verification.
Reboot recovery must reopen each Claude/Codex conversation by its exact saved ID;
restore layouts separately and report missing IDs instead of resuming the latest.
Reviews must support inline line/range comments and feedback for the correct task.
Review locally before opening a PR or starting an internal code review; no remote
review object is required. Keep comments/progress private, return feedback to the
selected agent, and review its fixes. Publishing remains a separate user action.
Review queue, on-demand Git UI, focused agent reviews, and task worktree helpers
are proposed additions. Tuicr supplies local comment-based reviews and private, task-specific feedback.
Automatic attention events and worktree helpers remain open. Verify changed revisions
and saved comments; actual SSH clipboard still needs a client check.

## Devices

| Platform | Context | Access | Rollout |
| --- | --- | --- | --- |
| Current Ubuntu machine | Explicit per machine | Primarily SSH; also local | First |
| M4 Pro MacBook | Personal | Local | Second |
| M4 Pro MacBook | Work | Local | Later |
| Amazon Linux | Work | SSH | Later |

Work machines allow installation. Detect OS/version and architecture; choose
work/personal settings explicitly. Keep OS and connection method separate.

## Working rules

1. Make the smallest useful change. Research official documentation and add
   dependencies for concrete needs. Start with native zsh/tmux/Neovim configuration.
2. Use shared defaults with small platform differences and explicit local choices.
   Keep chezmoi templates simple; generated configurations must work independently.
3. Resolve latest stable upstream releases at installation time. Use official
   sources or maintained packages, verify downloads where supported, and record
   installed versions. Explain compatibility limits or packages lagging upstream.
4. Separate package installation from configuration application. No network calls,
   installations, or updates during normal shell/editor startup. Upgrade deliberately.
5. Measure startup, first-use latency, and idle resource use for relevant changes.
   Set budgets from the pilot baseline; shifting work to first use still has a cost.
6. Keep credentials, private keys, tokens, agent sessions, histories, private employer
   settings, and machine-specific Git identity outside Git. Document local overrides.
7. Repository editing and installation are separate. Honor existing authorization;
   do not infer permission to change the login shell or terminate sessions.
8. Preview installation, back up conflicts, support restoration, and make repeated
   runs safe. Preserve existing settings and running agent/tmux sessions.
9. Use repo-maintained inventory and verification commands where available. Agents
   choose installation commands at bootstrap using current official documentation.
   Keep this file updated; create directories only for real content and use native
   chezmoi naming.
10. Do not commit or push unless requested. Never rewrite archived branches.

## Durable learning

When a task reveals a stable, evidenced, actionable lesson, refine existing guidance
or add a brief entry here explaining why it matters and what future agents should do.
Consolidate duplicates and remove superseded lessons. Keep detailed tool procedures
in BOOTSTRAP.md and machine-specific records outside Git.

- Concurrent edits can invalidate saved snapshots. Reread affected files before
  editing and investigate snapshot mismatches; preserve current work when comparing
  against an earlier baseline.
- Helper names connect configuration and code. When renaming commands, update tmux
  bindings, sibling-helper lookups, and verification fixtures together; check the
  filenames and permissions generated by chezmoi.
- Empty/dead tmux panes may have no current path. Pass the selected launch folder
  explicitly and retain it privately for recovery and failure handling.
- Verification results belong to the files that were tested. State whether checks
  used the current worktree or a saved baseline, and verify relevant later changes
  before reporting them as passing.
- Use `list-clients` for an invoking client's pane/PID. `display-message -c`
  still resolves pane context separately and can mix another session into the result.
- Fzf matching is asynchronous. Selection-dependent actions must wait for the
  latest match before accepting; fast typing/pastes can otherwise act on an older row.
- Keep shortcuts in `home/dot_local/bin/tmux_keys.py`; regenerate with
  `python3 scripts/sync-tmux-keys.py`. Its `--check` mode and CI reject stale bindings/help.
  Apply the catalog, affected helpers, configuration, and cheatsheet together.
- Terminal control sequences can split words in captured PTY output. Normalize
  them before readiness checks, or timings can measure a later redraw instead.
- Match verification to the behavior we own. Use short isolated checks for simple
  configurations; retain regression scripts for custom helpers with meaningful
  failure modes. Avoid maintaining tests of upstream tools and plugins.
- Scoped chezmoi directory previews need `diff --recursive`; first application
  needs `--parent-dirs` when ancestors are missing. Verify nested files explicitly.

## Implemented and verification

Implemented: this guide and agent bootstrap instructions, the Claude import,
a read-only inventory, minimal tuicr configuration, the shared tmux baseline,
scratch tasks, an agent launcher with a folder picker, an on-demand task/agent
switcher, a minimal zsh setup, and a language-aware Neovim review/editing setup.
.chezmoiroot selects home/ as the source.
Run the inventory from the repo root with Python 3.8+:

```sh
python3 scripts/inspect-machine.py
python3 scripts/inspect-machine.py --json
```

The inventory checks OS, architecture, login shell, tool paths/versions, connection
markers, configuration presence, and legacy loader references. It prints no config
contents or connection addresses and does not source startup files or change setup.
Do not commit its output: executable paths are machine-specific.

Preview managed configuration from the repo root:

```sh
chezmoi --source="$PWD" --no-pager diff
```

The zsh setup uses native Vim editing (10 ms Escape timeout), menu completion,
shared private history, and a host/path/branch/error prompt without dirty-file
scans. Two installed plugins supply asynchronous history suggestions and syntax
highlighting. Cached fzf integration provides Ctrl+R, Ctrl+T, Alt+C, and fuzzy
completion; fd/fdfind avoids ignored/dependency/build paths. `gs/gd/gds/gw` expose
Git status/diffs/worktrees on demand. `v` in normal mode or Ctrl+X Ctrl+E edits
the command with the configured editor. Private overrides live in ~/.zshrc.local.
Mise shims are reused for interactive/login shells without prompt hooks;
non-interactive children retain inherited runtime paths. No startup installs,
updates, or network calls. See README.md for usage and BOOTSTRAP.md for assets.
Use the short shell verification recipe in BOOTSTRAP.md; no permanent plugin
test harness is maintained.
Ubuntu pilot, 2026-10-05: signed zsh 5.9.2, autosuggestions 0.7.1, and highlighting
0.8.0 are installed; shell files are applied through chezmoi. The user selected
zsh as the login/tmux default; the private tmux override preserves that choice.
The switch retained all nine live panes. Isolated checks passed for Vim editing,
prefix search, error status, completion, shared/private history, fuzzy shortcuts, linked worktree
branches, and chezmoi dry-run/reruns/override preservation/restoration.
With 10,000 synthetic history entries: warm readiness ~53 ms, uncached readiness
~231 ms, steady prompts ~25 ms, first completion ~44 ms, first fuzzy file selection
~39 ms; a one-second Linux idle CPU sample measured 0%. Adding 5,000 untracked
files did not materially change branch-prompt cost. Pilot budgets: warm readiness
75 ms, uncached 300 ms, steady prompts 40 ms, and first completion/navigation
100 ms, with no idle polling. These are initial Ubuntu checks; macOS, Amazon Linux,
real SSH clipboard, and multi-agent load measurements remain unverified.
The CLI pilot adds checksum-verified bat 0.26.1, fd 10.5.0, standalone ripgrep
15.2.0, zoxide 0.10.0, delta 0.20.1, and Neovim 0.12.5 in private versioned
directories; system packages remain available. Zsh aliases `cat` to bat with
plain styling/no pager, `v`/`vim` to Neovim, and `gdp` to a delta-paged diff.
`z`/`zi` jump to learned directories; `..`/`...` go up one/two levels. Zoxide's
cached integration records directory changes, with no idle prompt work. Official
completions are installed outside Git; jq 1.7 and htop 3.3.0 are reused.
Focused current-source checks passed for aliases/plain piping, jumps, fd excludes,
rg/delta, and scoped chezmoi preservation/reruns. Warm readiness measured ~54 ms,
uncached ~242 ms, steady prompts ~24 ms, and a directory change plus prompt ~40 ms;
idle CPU remained 0% in a one-second sample. Editor measurements follow below.

Neovim uses commented native defaults, EditorConfig, private persistent undo,
external-edit checks, explicit SSH OSC 52 copying, and built-in help. Space `?`,
`vc`, and `vl` open its cheatsheet, installed config, and language settings; managed
edits belong in `home/dot_config/nvim/`, private overrides in `init.local.lua`.
Native LSP supports Java, JS/TS/JSX/TSX, Rust, Python, HTML and Markdown. Mermaid
and language fences use native syntax; an after/ftplugin override stops Neovim
0.12's default Markdown Treesitter highlighting so the configured fences apply.
Servers reuse clients per project; files over 1 MiB/20,000 lines skip LSP. Java/Rust
analysis is offline, without automatic builds; project dependencies need separate
fetch/build steps. Java indexes use private per-checkout/editor caches to avoid
concurrent JVM workspace locks. Space `lt` disables/re-enables installed services.
Fzf-lua, Flash, Gitsigns and Conform load on shortcuts as native optional packages;
no editor installs/updates/network calls are configured. Git watching starts only
after Space `gg`. Space `=` formats manually with Prettier, Ruff, rustfmt or JDT.
See README.md and BOOTSTRAP.md for keys, installation, compatibility and limits.

Ubuntu editor pilot, 2026-10-06, Neovim 0.12.5: current-source isolated checks passed
for every server's diagnostics/semantic navigation, all listed fenced languages,
Mermaid filetypes, every formatter, actual fuzzy file/text selection, labeled jumps,
Git hunks, help/config keys, LSP toggling, private overrides, missing packages,
recursive chezmoi previews/dry-runs/reruns and conflict restoration. Native undo,
external changes, split navigation, and mapped UTF-8 line/visual OSC 52 sequences
passed disposable headless/PTY checks; real Neovim SSH clipboard delivery remains
unverified. First paint: clean/configured warm medians ~51/57 ms at 3,000 lines,
~54/62 ms at 30,000; configured first runs ~60/66 ms. File picker ~45–50 ms,
text search ~71–138 ms; a Markdown fixture with all nine fenced syntaxes painted
in ~157 ms, and explicit Ruff formatting took ~13–15 ms. A one-second idle sample
of the editor plus Pyright measured 0% CPU/~185 MiB RSS. Initial budgets: warm
code first paint/file picker 100 ms, text search/fenced Markdown 200 ms;
no custom idle polling.
Language-service readiness is separate: small fixtures took ~0.35–1.25 s except
Java (~4.1–4.5 s). Editor/server memory sampled ~107–752 MiB; one TypeScript worker
reduced its fixture from ~500 to ~294 MiB. Actual projects, concurrent editor/agent
load, physical terminals, macOS and Amazon Linux still need measurement. Installed
versions, integrity/commits, backups and detailed checks stay in private state;
no permanent upstream-plugin verification harness is maintained.

The tmux baseline uses Ctrl+A, stable task names, current-directory windows/splits,
vi copy mode, OSC 52 support, and a compact native Tokyo Night bottom status line
with an amber hostname highlight while the prefix is active
(session name on narrow terminals). Managed agent panes capture exact conversation
IDs privately; tmux-resurrect restores layouts and invokes exact-ID recovery.
The pilot keeps its pre-existing resurrect/continuum plugins in ~/.tmux.local.conf,
an unmanaged private override loaded beside ~/.tmux.conf. Its compatibility plugin
list supports the existing TPM version. Keep continuum loaded after status styling.

SSH clients: Ghostty on macOS and RootShell on iPad. Use native OSC 52; the pilot's
attached xterm-256color clients advertise `Ms` and `set-clipboard` is already on.
Private PTY checks passed for copy-mode v/y emitting OSC 52, UTF-8/multiline input,
and explicit client routing; no real clipboard contents were read. Local device paste
confirmation is pending. No new dependency, watcher, or tmux restart is needed.

| After Ctrl+A | Action |
| --- | --- |
| Ctrl+A | Send Ctrl+A to the application |
| ? | Shortcut cheatsheet; j/k scroll, / searches, q closes |
| c / \| / - | New window / horizontal split / vertical split |
| h/j/k/l / H/J/K/L | Move / resize panes |
| z / Tab | Zoom / previous window |
| s / w | Session / window picker |
| N (Shift+N) / b | Workspace launcher / return to the previous session |
| g / B (Shift+B) | Search existing tasks/panes / return to the previous task |
| r | Local tuicr review popup; reports a missing tool |
| R | Reload installed tmux configuration |
| [ | Copy mode; v selects, y copies |

Ctrl+A, ? opens the managed ~/.config/tmux/cheatsheet.txt in less, on demand.
Apply that file with the tmux configuration; no help/history files are written at runtime.
Verified on an isolated server at 120x40 and 70x24: scrolling/search/close,
~26 ms first paint, chezmoi dry-run/reruns/restoration, and live-pane preservation.

Ctrl+A, Shift+N opens one Workspace menu. j/k chooses Scratch task (a private
folder and named window), New agent pane (another agent in the current window/folder),
or New session (a separate named session in the current folder). h/l switches
Codex/Claude; Enter opens; Esc/q cancels. Names support Backspace,
Ctrl+U to clear, Esc to go back, and Ctrl+C to cancel. Existing session names are
rejected without changing them; Ctrl+A, s switches sessions. New sessions reserve
the name scratch for scratch tasks. Inside the Workspace menu, g opens existing work.
Inside the popup, p immediately opens a pane, P asks for a pane name, s asks for
a new-session name, and t asks for a scratch-task name. These keys use the
selected/remembered agent; h/l changes it. While editing a name, letters are text.
p/P creates a real tmux split, starts the agent, and zooms it; Ctrl+A, z reveals
the full layout. Ctrl+A, | or - creates an ordinary shell split.
Named panes enable a compact top border caption in their own window. Their private
@dotfiles_pane_name label survives agent terminal-title changes and configuration
reloads; ordinary windows keep captions off. Recovery snapshots preserve these labels.
The former direct Ctrl+A, Ctrl+X/Ctrl+U agent launch bindings are removed.
The last launched tool is the default (initially Codex), saved privately in
~/.local/state/dotfiles/last-agent (or XDG_STATE_HOME). Cancelling, changing the
menu selection, reopening a live task, or a missing tool does not change it.
Scratch tasks use ~/workspace/scratch/<task>/ and named windows in the scratch
session. Reopening a live task preserves its window/conversation, regardless of
the menu's agent choice. Closing its window keeps files; reopening starts a fresh
conversation, not exact agent recovery.
The helpers run only on demand and require Python 3.8+ with curses, tmux, and Git.
The commands are `tmux-workspace`, `tmux-scratch`, `tmux-agent`, `tmux-tasks`, and `tmux-review`.
The menu waits for key input without polling; the recovery helper replaces itself with the CLI.
Apply the tmux configuration, all five helpers, and `tmux_keys.py` together.
Scratch roots inside Git checkouts are rejected. Override the root privately in
~/.tmux.local.conf with `set-environment -g DOTFILES_SCRATCH_ROOT '/absolute/path'`.
Inside the popup, f picks a folder for a new session and suggests its basename as
the session name; edit it or press Enter. Ctrl+F while naming a session changes its
folder without discarding the name. fzf supplies the search UI; the launcher supplies
its candidates and expands literal paths. Type to filter; Ctrl+j/k moves; Esc returns.
~ and ~/paths, absolute paths, and ./ or ../ paths work with Enter to select or Tab
to browse. The picker searches full absolute paths; a leading ~ expands to home.
Partial absolute or ~/ prefixes accept the highlighted completion. The naming screen
shortens home paths to ~/...; Tab browses one level (including hidden/linked folders),
and Alt+h goes to its parent. Invalid paths can be corrected in the picker.
The current folder remains the default for s. Search runs only on demand over
~/workspace (two levels, stopping at Git roots), the current folder, and up to 20
recent session folders stored privately in XDG_STATE_HOME/dotfiles/recent-folders.json.
The default project list skips hidden/build/dependency folders and symlinks. Override roots
privately with `set-environment -g DOTFILES_PROJECT_ROOTS '/absolute/root:/another'`.
The workspace picker adds no directory previews; zoxide integrates with zsh separately.
Ctrl+A, g opens the task switcher: search session/window/pane labels, tools, and
folders with fzf; Ctrl+j/k moves, Enter jumps, and Esc cancels. Alt+s opens a shell
split in the selected pane's folder; Ctrl+R opens its local review. Alt+n changes
its stable pane label. Alt+A hides/unhides a pane without stopping its process;
Alt+H includes hidden panes, and Ctrl+L refreshes the snapshot. Alt+b in the picker
or Ctrl+A, Shift+B returns to the exact previous pane reached through this switcher.
Linked windows retain the selected session context, and zoom is preserved.
Discovery reads only native tmux metadata, on demand. Unmarked panes show their
current command; live/exited labels do not infer whether an agent is busy or waiting.
Labels/hiding/history stay in private tmux options; hiding and previous-task history
reset when the server exits. Managed labels enter the next agent recovery snapshot.
Reviews open in the selected folder; multiple tasks sharing one checkout still
review the same changes until worktrees are added. Task worktrees, resource
associations, automatic attention events, and pane moves remain open.

Exact recovery is implemented for registered panes: lifecycle hooks record a UUID,
and layout saves freeze it with the folder, tool, and pane label in private snapshots.
Recovery runs `codex resume <UUID>` or `claude --resume <UUID>` without latest/fresh
fallbacks; missing state fails visibly. No watcher, transcript scanning, or idle polling.
Codex requires one-time hook trust via `/hooks`; its initial ID may appear only after
first submission. Existing live panes are preserved and need explicit UUID binding.
See BOOTSTRAP.md for setup, readiness checks, adoption, and save/restore controls.
Verified on Ubuntu with the installed resurrect plugin and two fake agents sharing
one folder: private server restart resumed both exact IDs/names/folders; repeated
restore kept running panes. Missing state/tools/folders/IDs, duplicate starts,
manual binding, additive settings/backups, and private modes passed. Installed Codex
0.160.1 and Claude 2.1.246 supplied native hook IDs/environment in disposable offline
fixtures using an unreachable localhost provider. Actual conversation recovery,
physical reboot, macOS, and Amazon Linux remain unverified.
Two synthetic launches took ~173–263 ms total, plugin save ~158–186 ms, restore ~441–468 ms.
These include the helper and installed plugin, exclude real agent/model work, and
are initial Ubuntu checks. The helper execs the CLI, leaving no Python supervisor per pane.

The pilot has checksum-verified fzf 0.74.4 installed; other platforms remain unverified.
Task-switcher checks use a private server and real fzf with synthetic commands;
they cover pane/session identity, zoom, linked windows, previous-task navigation,
shell/review folders, labels, reversible hiding, cancellation, missing dependencies,
literal paths, rapid query/action dispatch, and existing-process preservation.
Actual terminal testing is pending. On Ubuntu/tmux 3.4, repeated checks with two
attached clients passed: popup readiness ~73 ms, seven-row inventory ~3 ms, and a
one-second idle sample measured 0% across the server, picker, and helper processes.
Scoped chezmoi preview/dry-run/reruns/restoration passed. The pilot's new bindings
and helpers are applied with a private backup; all nine panes were preserved.
Only changed bindings were reloaded, retaining the existing continuum status hook.
The pilot's legacy plugin can skip adding that hook on a full reload when its
multiple-server guard fires; verify it after future full reloads.

Run the isolated tmux checks with Python 3.8+, tmux, Git, and fzf:

```sh
python3 scripts/verify-tmux.py
python3 scripts/verify-tasks.py
python3 scripts/verify-reviews.py
python3 scripts/sync-tmux-keys.py --check
```

Verified on Ubuntu/tmux 3.4: configuration reload, key dispatch, directory handling,
review popup, window renumbering, copy selection, and status at 120/70 columns.
Scratch checks cover the real popup/cancellation, return to the previous session,
multiple tasks, repeated opens, draft retention across closed windows, and path safety.
Launcher checks cover all three choices, Vim navigation, naming/back/cancel,
new-session folder preservation/name collisions, popup action keys, shared defaults,
named-pane validation/cancellation, visible captions despite terminal-title changes,
reload preservation, missing tools, startup failures, and existing pane/process retention.
Picker checks use real fzf in the popup: folder selection, current-folder defaults,
name preservation, cancellation, private recents, missing tools/invalid roots, literal
home/absolute/relative paths, absolute and ~/ prefix completion under home, pasted
paths, literal ~ in names, path correction, browsing/parent navigation, and isolation
from personal fzf options.
Synthetic commands never start a real agent or touch the real clipboard.
In the latest isolated check, the menu became visible in ~86 ms; scratch reopen
took ~44 ms, a synthetic agent launch ~79 ms, and named-pane launch ~46 ms.
The folder picker appeared in ~40 ms; the pilot folder scan took ~0.7 ms.
A two-second idle tmux CPU sample with captions visible measured 0%.
These timings exclude real agent startup; popup readiness includes terminal redraw.
These are initial sanity checks, not a multi-agent performance baseline.
Isolated chezmoi preview/dry-run/repeated apply, executable mode, backup/restoration,
and preservation of private overrides also passed for the tmux files and helpers.

The local review helper opens `tuicr -w --stdout --no-update-check` for the selected
checkout; `c`/`C` comments on a line/file and `v` then `c` selects a range.
Enter saves a comment; `ZZ` exports into private state and opens feedback actions:
`p` prepares a one-line prompt in the exact agent pane without Enter, `v` views
feedback, `r` reviews again, and `q` closes. `:q` leaves without exporting.
Preparation requires a captured conversation UUID, unchanged pane/process/record,
an active agent outside copy mode, and the same Git revision. Existing unmanaged
panes need explicit UUID binding; never infer their conversation from history.
Shared-checkout agents still see the same Git changes, but their comments/exports
are separate. Changed revisions get fresh comments; prior feedback stays archived.

Comments and immutable exports live under `$XDG_STATE_HOME/dotfiles/reviews/`
(default ~/.local/state/dotfiles/reviews), outside Git, with owned private directories
and 0600 exports/metadata. Tuicr data is isolated by task/conversation/revision;
its editor wrapper restores Neovim's ordinary HOME/XDG paths. The config uses
Tokyo Night, side-by-side diffs, and disables update checks and diff/review watchers.
No agent submission, remote review object, background watcher, or clipboard is needed.
Revision hashing runs on demand; untracked content is capped at 64 MiB per check.

Verified with official checksum-checked stable tuicr 0.27.0 on Ubuntu: real
file/line/range comments, clean export, per-agent isolation, unchanged-revision reopen,
fresh comments after moved lines, stale-ID/revision refusal, Git ignore settings,
editor environment, and bracketed preparation without Enter at 120x40/70x24 with
fake agents. Pilot installation/configuration/helpers/help are applied with private
backups; all nine panes, attached clients, the override, and continuum hook were retained.
Scoped chezmoi dry-run/reruns/restoration passed. Rendered review readiness ~105–135 ms,
revision hashing ~6 ms on a small fixture, sampled one-second idle CPU 0%.
These exclude real agent/model work and are not large-project performance budgets.
Real SSH clipboard, physical terminal behavior, and real-agent input remain unverified.
The private wrapper requires Linux XDG storage; macOS isolation needs implementation
and verification before rollout (plain `tuicr -w` remains usable there).

For inventory changes, check syntax and both output modes. Test helper changes
and chezmoi previews/repeated runs with isolated home/config/state directories,
without package installs or live session changes. Report actual checks and limits.
Verification so far is limited to Ubuntu; macOS/Amazon Linux verification is pending.

## Pilot snapshot: 2026-10-02

Ubuntu 24.04.4 LTS, x86_64, SSH, Bash login shell. Installed: chezmoi 2.72.0,
tmux 3.4, Neovim 0.9.5, Git 2.43.0, ripgrep 15.2.0 (from Codex), fdfind 9.0.0,
mise 2026.8.10, Codex 0.160.0, Claude Code 2.1.246. Zsh, fzf, and fd command missing.
Node/Python use mise; respect existing ownership before adding a runtime manager.

No user Neovim or chezmoi configuration
directory was observed. Startup timing and clipboard/session behavior are unverified.
These are observed versions, not installation targets; tmux is now applied as above.

## Milestones

1. **Done:** agree on vision/devices/priorities, add agent guidance and inventory,
   and inspect this machine.
2. **In progress:** tmux controls/UI/review shortcut are verified; the baseline is
   applied and reloaded on the pilot with existing layout persistence preserved.
   Scratch organization, one Vim-style launcher with remembered agent selection,
   named-pane captions, the folder picker, and task/agent navigation are implemented.
   Exact-ID recovery is implemented and tested on an isolated server; native hook
   capture passed offline checks. **Next:** real conversation recovery verification,
   then reliable attention events and task worktrees. Local review/feedback and generated
   shortcut help are implemented; actual user-terminal checks remain.
   Use the home/ chezmoi source and add stable tool setup needed for this milestone.
   Measure overhead; test recovery on an isolated server before applying changes.
   Verify previews, preservation/restoration, and reruns.
3. Minimal zsh and project/file navigation with performance measurements; verify
   clipboard with the actual terminal/SSH client. Zsh and fuzzy shell navigation
   are implemented; broader navigation and review/worktree feature choices remain.
4. **Implemented on Ubuntu:** Neovim language services, on-demand navigation/review
   plugins, manual formatting and self-documenting config/help. Native and plugin
   fixture measurements are recorded above; representative projects, simultaneous
   editors/agents, physical terminal behavior and other platforms remain to verify.
5. Verify onboarding on the personal MacBook, then work devices.

Open discovery: checkout roots, existing agent/worktree/session practices, terminal
clients, session naming/resume needs, development languages, and secret storage.
Agent bootstrap guidance is implemented; broader configuration, backups/restoration,
and benchmarks are planned. Bootstrap on additional platforms remains unverified.

## Primary references

- [Chezmoi](https://www.chezmoi.io/user-guide/command-overview/),
  [machine differences](https://www.chezmoi.io/user-guide/manage-machine-to-machine-differences/),
  [installation](https://www.chezmoi.io/install/), and
  [source layout](https://www.chezmoi.io/user-guide/advanced/customize-your-source-directory/).
- [fzf](https://github.com/junegunn/fzf) and
  [zoxide](https://github.com/ajeetdsouza/zoxide) (folder-discovery research).
- [Zsh](https://zsh.sourceforge.io/Doc/Release/Files.html),
  [tmux](https://github.com/tmux/tmux/wiki/Getting-Started),
  [Neovim](https://github.com/neovim/neovim/blob/master/INSTALL.md), and
  [Git worktrees](https://git-scm.com/docs/git-worktree).
- [Codex instructions](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
  and [Claude imports](https://code.claude.com/docs/en/memory).
- [fzf picker actions](https://github.com/junegunn/fzf/blob/master/man/man1/fzf.1)
  and [tmux client formats](https://github.com/tmux/tmux/blob/master/cmd-list-clients.c).
- [Tuicr](https://github.com/agavra/tuicr) and
  [configuration](https://github.com/agavra/tuicr/blob/main/docs/CONFIG.md).
