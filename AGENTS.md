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
are proposed additions. Tuicr is the starting tool for local comment-based reviews;
agent attention shortcuts and feedback handoff are not implemented yet. Verify
saved comments, revision changes, and SSH clipboard before applying it to this machine.

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
- Match verification to the behavior we own. Use short isolated checks for simple
  configurations; retain regression scripts for custom helpers with meaningful
  failure modes. Avoid maintaining tests of upstream tools and plugins.

## Implemented and verification

Implemented: this guide and agent bootstrap instructions, the Claude import,
a read-only inventory, minimal tuicr configuration, the shared tmux baseline,
scratch tasks, and an agent launcher
with an optional folder picker, and a minimal zsh setup.
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
idle CPU remained 0% in a one-second sample. Clean headless Neovim opened a
3,000-line fixture in ~4–5 ms; interactive rendering/plugins are not measured.

The tmux baseline uses Ctrl+A, stable task names, current-directory windows/splits,
vi copy mode, OSC 52 support, and a compact native Tokyo Night bottom status line
with an amber hostname highlight while the prefix is active
(session name on narrow terminals). Managed agent panes capture exact conversation
IDs privately; tmux-resurrect restores layouts and invokes exact-ID recovery.
The pilot keeps its pre-existing resurrect/continuum plugins in ~/.tmux.local.conf,
an unmanaged private override loaded beside ~/.tmux.conf. Its compatibility plugin
list supports the existing TPM version. Keep continuum loaded after status styling.

| After Ctrl+A | Action |
| --- | --- |
| Ctrl+A | Send Ctrl+A to the application |
| c / \| / - | New window / horizontal split / vertical split |
| h/j/k/l / H/J/K/L | Move / resize panes |
| z / Tab | Zoom / previous window |
| s / w | Session / window picker |
| N (Shift+N) / b | Workspace launcher / return to the previous session |
| r | Local tuicr review popup; reports a missing tool |
| R | Reload installed tmux configuration |
| [ | Copy mode; v selects, y copies |

Ctrl+A, Shift+N opens one Workspace menu. j/k chooses Scratch task (a private
folder and named window), New agent pane (another agent in the current window/folder),
or New session (a separate named session in the current folder). h/l switches
Codex/Claude; Enter opens; Esc/q cancels. Names support Backspace,
Ctrl+U to clear, Esc to go back, and Ctrl+C to cancel. Existing session names are
rejected without changing them; Ctrl+A, s switches sessions. New sessions reserve
the name scratch for scratch tasks. Ctrl+A, g is unbound.
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
The commands are `tmux-workspace`, `tmux-scratch`, and `tmux-agent`. The menu waits
for key input without polling; the recovery helper replaces itself with the CLI.
Apply the tmux configuration and all three helpers together.
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
The task/resource picker, archival controls, and pane moves remain future work.

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

Run the isolated tmux checks with Python 3.8+, tmux, Git, and fzf:

```sh
python3 scripts/verify-tmux.py
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

The tuicr config selects Tokyo Night, side-by-side diffs, and Neovim for file
navigation. It disables startup update checks and background diff/review polling.
Tuicr's local comments/progress stay in its data directory outside Git.
Tuicr remains a temporary trial binary. The pilot's
tmux config is applied through chezmoi, backed up under ~/.local/state/dotfiles/backups/,
and reloaded without replacing live panes. All three tmux helpers are applied under
~/.local/bin/. The tuicr config is not applied yet.
After tool installation, `tuicr -w` opens local changes; `c` adds a comment and
`ZZ` exports and exits. `:q` exits without exporting; `--stdout` redirects exports
to stdout for a future feedback handoff.

Verified on Ubuntu with a checksum-checked temporary tuicr 0.27.0 binary: chezmoi
preview/dry-run/repeated apply, file/line/range comments, untracked files, saved
comments across reopen, Markdown export, and refreshed diffs on reopen. Real SSH
clipboard, moved-line comment anchors, and real-terminal performance remain unverified.

For inventory changes, check syntax and both output modes. Test helper changes
and chezmoi previews/repeated runs with isolated home/config/state directories,
without package installs or live session changes. Report actual checks and limits.
Verification so far is limited to Ubuntu; macOS/Amazon Linux verification is pending.

## Pilot snapshot: 2026-10-02

Ubuntu 24.04.4 LTS, x86_64, SSH, Bash login shell. Installed: chezmoi 2.72.0,
tmux 3.4, Neovim 0.9.5, Git 2.43.0, ripgrep 15.2.0 (from Codex), fdfind 9.0.0,
mise 2026.8.10, Codex 0.160.0, Claude Code 2.1.246. Zsh, fzf, and fd command missing.
Node/Python use mise; respect existing ownership before adding a runtime manager.

The Bash loader still references deleted shell/ipad.sh; address it during migration
with backups. The legacy tmux/scrolling.conf loader was replaced with a backup.
No user Neovim or chezmoi configuration
directory was observed. Startup timing and clipboard/session behavior are unverified.
These are observed versions, not installation targets; tmux is now applied as above.

## Milestones

1. **Done:** agree on vision/devices/priorities, add agent guidance and inventory,
   and inspect this machine.
2. **In progress:** tmux controls/UI/review shortcut are verified; the baseline is
   applied and reloaded on the pilot with existing layout persistence preserved.
   Scratch organization, one Vim-style launcher with remembered agent selection,
   named-pane captions, and the folder picker are implemented.
   Exact-ID recovery is implemented and tested on an isolated server; native hook
   capture passed offline checks. **Next:** real conversation recovery verification,
   then task/agent navigation and feedback handoff.
   Use the home/ chezmoi source and add stable tool setup needed for this milestone.
   Measure overhead; test recovery on an isolated server before applying changes.
   Verify previews, preservation/restoration, and reruns.
3. Minimal zsh and project/file navigation with performance measurements; verify
   clipboard with the actual terminal/SSH client. Zsh and fuzzy shell navigation
   are implemented; broader navigation and review/worktree feature choices remain.
4. Minimal Neovim review/editing setup; measure representative projects before plugins.
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
- [Tuicr](https://github.com/agavra/tuicr) and
  [configuration](https://github.com/agavra/tuicr/blob/main/docs/CONFIG.md).
