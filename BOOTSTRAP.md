# Tool requirements and agent bootstrap

Follow [AGENTS.md](AGENTS.md) for project context and working rules.

Bootstrap is an agent-run workflow. This file describes required capabilities;
the agent selects installation methods for the actual machine at bootstrap time.
Repository scripts provide inventory and verification; the agent performs
installation using current official sources. Keep machine/package-manager decisions
out of shared startup files.

## Tool requirements

Choose tools by the requested features and confirm requirements against the managed
configuration and helpers. Pilot snapshot versions in AGENTS.md are observations,
not targets.

| Scope | Tools/capabilities | Purpose |
| --- | --- | --- |
| Configuration management | Git, chezmoi | Repository access, configuration preview/application |
| Shared tmux setup | tmux | Sessions, panes, popups; verified with 3.4, other versions need checks |
| Shortcut cheatsheet | less | On-demand scrolling/search; manage ~/.config/tmux/cheatsheet.txt with the tmux configuration |
| Workspace/session/scratch helpers | Python 3.8+ with curses, tmux, Git | Launcher/session UI and scratch-folder safety; apply the tmux configuration and all seven helpers plus `tmux_keys.py` together |
| Agent launching/recovery | Selected Codex and/or Claude Code CLI with SessionStart hooks; tmux-resurrect for layouts | Available in tmux's PATH; exact IDs and credentials stay private |
| Agent attention | Native Codex/Claude hooks, Python, tmux; fzf for the queue | Shared event reducer and cached native status; no daemon or transcript inspection |
| Agent status lines | Native Codex footer; POSIX sh, jq, Git for Claude; Python 3.11+ during setup only | Model/effort/context/branch; explicit personal mode adds subscription headroom |
| Fuzzy selection | fzf | Shell history/file/directory selection, zoxide's `zi`, tmux folder/task pickers, and the full tmux verification suite |
| Local reviews | tuicr, Neovim (`nvim`), Git, less | Private local comments/export and guarded feedback preparation; the editor wrapper keeps normal Neovim paths |
| Interactive shell | Current stable Zsh, zsh-autosuggestions, zsh-syntax-highlighting; fzf integration; fd/fdfind when available | Native Vim editing/completion/history, suggestions/highlighting, on-demand fuzzy navigation |
| CLI essentials | bat, fd, ripgrep, zoxide, delta, Neovim | Read files, find code, jump directories, inspect diffs, edit |
| JSON inspection | jq | Inspect and transform structured CLI output; reuse a suitable existing installation |
| Resource inspection | htop | Inspect agent/process CPU and memory on demand; reuse a suitable existing installation |
| Editor setup | Stable Neovim 0.11+, ripgrep, fzf; fzf-lua, Flash, Gitsigns, Conform | Native LSP/undo/clipboard; on-demand discovery, jumps, hunks, manual formatting |
| Editor language services | typescript-language-server + compatible TypeScript, Pyright, vscode-langservers-extracted, rust-analyzer + rust-src, JDT LS + supported JDK, Marksman | Java/JS/TS/JSX/TSX/Rust/Python/HTML/Markdown analysis; Mermaid uses native syntax |
| Explicit editor formatting | Prettier, Ruff, rustfmt; JDT LSP for Java | Format only on request; project settings apply |
| Future task workflows | Task worktrees/resource associations | Broader task organization remains planned |

Managed helper sources are `home/dot_local/bin/executable_tmux-workspace`,
`executable_tmux-scratch`, `executable_tmux-agent`, `executable_tmux-tasks`,
`executable_tmux-review`, `executable_tmux-attention`, and `executable_tmux-sessions`
with the shared `tmux_keys.py` catalog. Chezmoi's [`executable_` attribute](https://www.chezmoi.io/reference/source-state-attributes/)
marks executable permissions; the installed commands are `~/.local/bin/tmux-workspace`
`~/.local/bin/tmux-scratch`, `~/.local/bin/tmux-agent`, `~/.local/bin/tmux-tasks`,
`~/.local/bin/tmux-review`, `~/.local/bin/tmux-attention`, and `~/.local/bin/tmux-sessions`.
When updating an older setup, back up the retired `dotfiles-agent` and
`dotfiles-scratch` helper files and remove them after verifying the new bindings.

The managed shell sources are `home/dot_zshenv` and `home/dot_zshrc`.
Install tagged stable plugins under `$XDG_DATA_HOME/zsh/plugins/` (default
`~/.local/share/zsh/plugins/`), keeping the upstream directory names
`zsh-autosuggestions` and `zsh-syntax-highlighting`. Generate `fzf --zsh` into
`$XDG_DATA_HOME/zsh/fzf.zsh` during installation and regenerate it when upgrading
fzf. No plugin manager or download runs at startup. Reuse an existing runtime
manager; mise's shims are supported without activation hooks. Private settings
belong in `~/.zshrc.local`; preserve existing startup files and inspect `ZDOTDIR`
before applying. Applying configuration does not change the login shell or
tmux's default shell. See [README.md](README.md) for features and scoped previews.
Generate `zoxide init zsh --hook pwd` into `$XDG_DATA_HOME/zsh/zoxide.zsh` during
bootstrap and when upgrading zoxide. Copy upstream zsh completion files into
`$XDG_DATA_HOME/zsh/site-functions/`. These are installed artifacts outside Git.
On the Ubuntu pilot, official checksum-verified binaries use versioned
`~/.local/opt/` directories and command links in `~/.local/bin/`; system packages
are preserved. Select suitable current official installation methods per platform.
After explicit authorization, register the stable zsh path with the OS, change
the account's login shell, and record `default-shell` in the private tmux override.
Set the live server's default for future panes without replacing existing panes.

Editor sources live under `home/dot_config/nvim/`: commented `init.lua`, the
`lua/dotfiles/` language/plugin modules, and native `doc/dotfiles.txt` help. Apply
them together, preserving existing configuration and the unmanaged `init.local.lua`.
Respect XDG paths and inspect NVIM_APPNAME before application. Directory previews
need `diff --recursive`; scoped first applies need `--parent-dirs` to create missing
config ancestors. Generate help tags once
after installation with `nvim --headless -u NONE -c 'helptags ~/.config/nvim/doc' -c qa`
(adjust the path for XDG/NVIM_APPNAME). See README.md for scoped preview/application.
Native filetype support/EditorConfig sets indentation. SSH copying uses native
OSC 52/getregion; the pilot uses Neovim 0.12.5. Native LSP needs 0.11+; older editors
retain basic editing without language clients. Plugin compatibility needs checking.

Install editor plugins under `$XDG_DATA_HOME/nvim/site/pack/dotfiles/opt/` (default
`~/.local/share/nvim/site/pack/dotfiles/opt/`). Use current stable Flash, Gitsigns,
and Conform tags. Fzf-lua has no current stable release series: resolve and record
a maintained upstream commit rather than its obsolete 0.7 tag. The pilot uses
versioned checkouts with command-free package links; `packadd` runs only on first use.
There is no startup plugin manager, network call, installation, or update.

Resolve language-server/formatter versions from their official sources during
bootstrap. Install the Node tools with the existing Node manager and a private npm
prefix; preserve the lockfile and registry integrity metadata. Current
[typescript-language-server](https://github.com/typescript-language-server/typescript-language-server)
requires TypeScript 6's JavaScript server and Node 22.22.2+; use the newest compatible
stable versions rather than installing incompatible TypeScript 7. Use official
release digests for [Marksman](https://github.com/artempyanykh/marksman) and
[Ruff](https://docs.astral.sh/ruff/installation/). Verify the stable
[JDT LS milestone](https://github.com/eclipse-jdtls/eclipse.jdt.ls) checksum; its
launcher requires Java 21+. Keep its launcher JDK separate from project JDKs and
pass a private per-checkout/editor `-data` cache workspace to avoid simultaneous
JVM lock conflicts. The pilot's versioned launcher records
its JDK/path privately and provides `jdtls --version` without starting a JVM.

Reuse mise ownership for Java/Rust installations without changing existing global
runtime selections. Rust needs cargo/rustc, rust-analyzer, rust-src and rustfmt;
resolve a stable toolchain and add those components during bootstrap. The pilot
uses direct installed toolchain binaries as a stable fallback, with no rustup
installation during editor startup. Select different project runtimes through mise
and private LSP settings. Java/Rust defaults disable automatic builds/downloads;
fetch/build project dependencies explicitly outside the editor. See the native
cheatsheet for offline-analysis limits and override examples. Record all versions,
paths, integrity/commits, command-link restoration and backups privately.

## Bootstrap procedure

When asked to bootstrap:

1. Inspect Git status and the machine without changing it. Detect OS/version,
   architecture, connection method, available tools, existing configuration and
   runtime/package-manager ownership. Establish work/personal context and feature
   scope from the request; ask only for missing choices. Use the inventory helper
   when Python is available, otherwise use native read-only commands first.
2. Research current official installation documentation and latest stable releases
   for the needed tools. Choose maintained packages or official binaries suitable
   for this machine; explain upstream lag or compatibility limits. Reuse suitable
   existing tools and runtime managers; upgrades are deliberate. Add build/runtime
   dependencies only when the selected installation method requires them.
3. Describe the concrete installation and configuration changes, then proceed within
   the user's bootstrap authorization. Preserve existing settings and live sessions;
   changing the login shell or terminating sessions needs explicit authorization.
   Back up conflicts outside Git and identify how to restore them.
4. Install dependencies separately from chezmoi application. Verify downloads where
   supported and check executable versions and paths, including tmux's environment.
   Record installed versions, sources/methods, and backup/restoration details privately
   in `$XDG_STATE_HOME/dotfiles/` (default `~/.local/state/dotfiles/`), preserving
   existing records.
   Keep credentials and agent authentication outside the repository.
5. Preview the requested managed files with chezmoi, then apply only the selected
   scope. Use isolated configuration checks before changing live setup. Verify
   repeated application and preservation of private overrides; keep installation,
   network calls, and updates out of normal startup.
6. Run applicable repo verification commands and check the selected features with
   real tool versions. Measure relevant startup/first-use/idle costs. Report installed
   versions, changes, restoration paths, skipped features, and actual verification
   limits; real SSH clipboard and agent recovery require their own checks.

## Session ordering and pane movement

Ctrl+A, s uses the curses `tmux-sessions` popup; apply that executable,
`tmux_keys.py`, the tmux configuration and cheatsheet together. Letter keys and
custom ordering are private, keyed by session name rather than reboot-sensitive
native IDs. Preferences live in `$XDG_STATE_HOME/dotfiles/sessions/` (default
`~/.local/state/dotfiles/sessions/`): owned 0700 directory, 0600 JSON/lock, locked
read/merge/atomic writes. No watcher, polling or new package is needed. Preserve
the JSON when restoring/migrating layouts; renaming a session creates a new entry.
An explicit key assignment can reclaim a closed session's key; active duplicates
are refused. See README.md and Ctrl+A, ? for the popup controls.
Inside the picker, j/k selects down/up, J/K reorders down/up, and e edits a
shortcut. Previously saved e/J/K shortcuts migrate to available letters while
preserving session order and unaffected keys; blank shortcuts remain blank.

Shift-arrow pane swaps use native tmux commands, capture the invoking pane's
exact ID, keep its focus, reveal zoomed layouts and stop at outer edges. IDs,
processes and pane-local options survive swapping. Run
`python3 scripts/verify-sessions.py` for isolated two-client picker/order/key,
concurrent preference writes, and spatial-pane checks at 120/70 columns. Physical
terminal delivery of modified arrows remains a client check. On the Ubuntu pilot,
reload only the changed bindings to preserve the legacy continuum status hook;
after any full configuration reload, check that the hook is still present.
Pilot backups live under `$XDG_STATE_HOME/dotfiles/backups/tmux-sessions-*/`.
The private manifest records original files/modes (or new targets) and the five
prior bindings. Restore those files and bindings, unbinding keys previously absent;
retain intervening private changes. No full reload or session restart is required.

## Nested tmux checks

Keep the shared Ctrl+A default on the outer server. For a separate inner server,
preview/apply the profile, help and catalog together:

```sh
chezmoi --source="$PWD" --no-pager diff ~/.config/tmux/inner.conf ~/.config/tmux/cheatsheet.txt ~/.local/bin/tmux_keys.py
chezmoi --source="$PWD" apply --dry-run --parent-dirs ~/.config/tmux/inner.conf ~/.config/tmux/cheatsheet.txt ~/.local/bin/tmux_keys.py
chezmoi --source="$PWD" apply --parent-dirs ~/.config/tmux/inner.conf ~/.config/tmux/cheatsheet.txt ~/.local/bin/tmux_keys.py
```

The profile is generated from
the shortcut catalog; `sync-tmux-keys.py --check` checks it too. Back up any
conflicting targets and the existing private `~/.tmux.local.conf`, then add
`source-file ~/.config/tmux/inner.conf` at the end of that override. Source only
the profile for live activation, avoiding a full plugin reload:

```sh
tmux source-file ~/.config/tmux/inner.conf
tmux show-options -Av prefix
```

The expected prefix is `C-b`. This sets the server's global session default and
changes its prefix-table Ctrl+A/Ctrl+B bindings; other clients on that server
share those bindings. Existing session-local prefix overrides retain their own
values. Use a separate `tmux -L inner` server for two roles on the same machine;
load the inner profile only into that server rather than persisting it for both.
Do not infer the role from SSH or change the outer server while configuring it.

For restoration, remove the added source line (preserving other private edits),
restore the previous prefix option and Ctrl+A/Ctrl+B bindings. For the shared
baseline these are `set -g prefix C-a`, `unbind -q C-b`, and `bind C-a send-prefix`.
No session restart is needed. Preserve any pre-existing session overrides.

From a shell in each layer, record the terminal app, tmux version, effective mouse
setting and wheel bindings before changing configuration:

```sh
tmux -V
tmux show-options -Av mouse
tmux list-keys -T root | rg 'WheelUpPane|WheelDownPane'
printf 'TERM=%s\n' "$TERM"
```

Use `tmux set-option mouse on` in a layer whose effective setting is off; this
changes that session, so account for other clients sharing it. Persist the setting
in the appropriate managed configuration/private override. Native wheel bindings
use `send-keys -M` when the application requests mouse input. Compare custom wheel
bindings before replacing them. Keep a tmux/screen terminfo entry inside tmux and
ensure the remote host has the client terminal's entry; do not force xterm in shell
startup files. See the [tmux mouse manual](https://man.openbsd.org/tmux.1#MOUSE_SUPPORT)
and [terminal guidance](https://github.com/tmux/tmux/wiki/FAQ#what-is-term-and-what-does-it-do).

With the inner profile, Ctrl+B addresses the inner server directly. If both
layers use Ctrl+A, Ctrl+A Ctrl+A sends one prefix to the inner client;
the next key controls that layer. Blanket nesting toggles that change global/session
prefix, mouse or key-table options also affect other clients of that session.
Verify scope and restoration before adopting such a toggle. Ubuntu/tmux 3.4 isolated
nested PTYs passed inner wheel scrolling and double-prefix copy mode; disabling
inner mouse reproduced outer copy-mode capture. Current-source inner-profile checks
also passed separate Ctrl+A/Ctrl+B dispatch, literal Ctrl+B delivery, repeat loading,
full baseline reload with the private source line, pane/PID preservation and scoped
chezmoi preview/dry-run/rerun/conflict restoration. Profile loading took ~2.5 ms
including the tmux command process; it adds no startup subprocess or idle work.
Work-machine terminals remain unverified.

## Agent recovery setup

Apply the tmux configuration and all seven helpers plus `tmux_keys.py` together. Install tmux-resurrect
and optionally continuum separately; keep the pilot's existing private TPM loader.
The shared config uses resurrect's post-save-layout hook to replace only managed
agent commands with immutable recovery snapshots. Private overrides load last;
preserve existing process lists/hooks when integrating on another device. An existing
custom post-save-layout hook must call our helper too, with the layout filename.

Preview `tmux-agent setup --dry-run`, then run `tmux-agent setup` at bootstrap.
It adds one SessionStart hook to Codex's hooks.json and Claude's settings.json,
merging existing keys and backing up originals with restoration manifests privately.
Honor CODEX_HOME/CLAUDE_CONFIG_DIR. These merged settings are installation artifacts,
not whole-file chezmoi targets. [Codex hooks](https://learn.chatgpt.com/docs/hooks)
require the user to review/trust the hook through
`/hooks`; do not bypass hook trust during normal launches. A first untrusted launch
may need explicit binding or a subsequent session after trust. Codex 0.160.1 creates
its initial thread/hook on first submission; an unused pane may have no ID yet.
Managed sessions retain their normal CLI model, permission, and authentication settings.
Keep an unset `CLAUDE_CONFIG_DIR` unset: explicitly exporting `~/.claude` also moves
Claude's global `.claude.json` lookup into that directory. New records distinguish
unset from explicitly selected paths. Older snapshots retain custom directories;
their default `~/.claude` path is treated as unset because the original choice was
not recorded. See [Claude configuration locations](https://code.claude.com/docs/en/claude-directory).

`tmux-agent status` lists live managed panes and capture readiness. Existing unmanaged
conversations can be registered explicitly with
`tmux-agent bind codex <conversation-UUID> --pane %N` (or claude), without restarting.
Manual bindings must be updated after switching conversations. Do not infer an ID
from the newest transcript, history, or shared working folder.
Records/snapshots live in `$XDG_STATE_HOME/dotfiles/agents/` with private modes.
Resurrect's Ctrl+A Ctrl+S saves layouts; Ctrl+A Ctrl+R restores. Continuum saves on
its existing interval. Missing metadata, folders, tools, or conversations must fail
visibly; never substitute a fresh/latest conversation. Missing tool-owned conversation
history is reported by the CLI's exact-ID lookup. Keep agent histories and recovery
state when migrating/restoring this machine. Session layouts do not sync between devices.

For rollback, restore backed-up contents/modes and remove targets recorded as new.
The pilot apply manifest records the previous tmux global options: restore their
values or unset absent options, then source the previous tmux config. Restore the
separate hook-setup manifests too before removing the recovery helper.

Run `python3 scripts/verify-agent-recovery.py --resurrect <installed-plugin-directory>`
for fake Codex/Claude capture, two agents sharing a folder, immutable snapshots,
private server restart, real plugin restore, duplicate/missing-state failures,
manual adoption, private settings merging/backups, and repeatability. Use
`python3 scripts/verify-tmux.py` for launcher/picker checks. No real conversations
or reboot are exercised by these scripts; verify an actual recovery deliberately.

For a real recovery drill, first check `codex login status` and `claude auth status`;
complete authentication in the ordinary CLI. Use disposable conversations, a private
tmux socket, separate helper state and resurrect layouts, and explicit test folders.
Do not source the live private override/continuum loader into that test server.
Give two conversations in the same folder different markers, save only after their
exact IDs are ready, restart only the test server, and restore through resurrect.
Compare each CLI's native session ID with its saved UUID and ask it to recall its
marker without repeating the marker or allowing file/tool access. Restore again
and confirm existing pane PIDs stay unchanged. Never read unrelated histories.
Leave hook review to the user; explicit UUID binding can verify recovery separately.
Codex may show update/hook review prompts. If it reports incompatible shared daemon
settings, choose its per-invocation **Run without daemon** option rather than
restarting a daemon used by active sessions. Record tool versions on both sides.

## Agent status-line setup

Apply only the `claude-statusline` renderer after a scoped preview:

```sh
chezmoi --source="$PWD" --no-pager diff ~/.local/bin/claude-statusline
chezmoi --source="$PWD" apply --dry-run --parent-dirs ~/.local/bin/claude-statusline
chezmoi --source="$PWD" apply --parent-dirs ~/.local/bin/claude-statusline
python3 scripts/setup-agent-statusline.py --mode personal --dry-run
python3 scripts/setup-agent-statusline.py --mode personal
```

Select `--mode work` explicitly on work devices; context is never inferred from OS,
hostname, checkout or authentication. Work omits usage/cost; personal shows supplied
subscription limits rather than reconstructing them from tokens or transcripts.
The native Codex items are model-with-reasoning, context-remaining, git-branch and
fast-mode; personal adds five-hour-limit and weekly-limit before branch.
Compatible pilot versions are Codex 0.160.1 and Claude 2.1.246. Further versions
need field/width checks; quotas depend on the account/provider and first response.

The setup script validates all targets before writing, preserves unrelated settings
and TOML comments, backs up changed files, then writes atomically per file. It
honors CODEX_HOME, CLAUDE_CONFIG_DIR, XDG_CONFIG_HOME and XDG_STATE_HOME; all directory
overrides must be absolute. Repeated runs leave identical files untouched. Ordinary
`[tui]` tables and root dotted keys are supported; unusual inline/quoted table forms
fail without changes rather than reserializing private configuration. `--renderer`
selects a different installed executable. Claude gets a direct, quoted command with
no refreshInterval; nothing is installed or updated by rendering or setup.

Backups live under `$XDG_STATE_HOME/dotfiles/backups/agent-statusline-*/` in 0700
directories with 0600 originals/manifests. Each manifest entry records `target`,
`existed`, original `mode`, and its `backup` filename. To restore, copy an entry's
saved bytes to its target and restore that mode; remove targets recorded as new.
Review any intervening private changes before restoration. Back up a conflicting
renderer separately before chezmoi application; restoration of that helper is
separate from agent settings. Keep all backups and machine results outside Git.

Run `python3 scripts/verify-statusline.py` for our rendering, private-mode selection,
widths/colors, branch identity, missing/zero metrics, additive configuration,
preview/reruns, malformed targets and restorable backups. Use disposable homes
with isolated HOME/XDG/CODEX_HOME/CLAUDE_CONFIG_DIR for chezmoi preview/dry-run/
repeated application and conflict restoration. Measure actual renderer cost and
verify installed versions in an isolated terminal; never restart or type into live
agent conversations for a check. No upstream plugin test harness is involved.
Claude width comes from COLUMNS, without tput; Unicode is bounded conservatively by
UTF-8 byte length. Physical terminals and other platforms need their own checks.

## Agent attention setup and event contract

Preview `tmux-attention setup --dry-run`, then run `tmux-attention setup` after
applying the helpers. `--agent codex` or `--agent claude` scopes the merge.
This adds advisory hooks while preserving other handlers/settings, including
handlers sharing a group, and writes originals plus manifests under private
`$XDG_STATE_HOME/dotfiles/backups/attention-hooks-*/`. Restore original bytes/modes
from those manifests; remove targets recorded as new. Repeated setup is safe.
SessionStart reuses the recovery capture command to avoid racing identity capture.
Codex requires review/trust of the added commands through `/hooks` in a new session;
Claude loads the settings for subsequent sessions. Keep ordinary permission policy.

Attention applies to invocations started by our launcher after this update. Existing
panes keep running and show unavailable status; manual UUID binding alone cannot
add the launch nonce/runtime context to an already running process. Do not infer
identity from transcripts. Attention survives SSH detach in private tmux options,
but resets on a new invocation/server restart and is not resurrected as old alerts.
The only disk artifact is a private per-server lock; no event log is maintained.
Native lifecycle hooks clean closed panes; `tmux-attention refresh` reconciles state
on demand after manual pane respawns. Array slot 1701 preserves other tmux hooks.

Adapters translate [Codex hooks](https://learn.chatgpt.com/docs/hooks) and
[Claude hooks](https://code.claude.com/docs/en/hooks) into these shared events:

| Event | Additional metadata | Meaning |
| --- | --- | --- |
| `session_started` | None | Initialize a captured conversation |
| `turn_started` | `turn_id` when available | Clear old alerts/input and report working |
| `input_requested` | `request_id`, `reason`, optional `tool` | Pending approval/question/plan/elicitation |
| `input_resolved` | Same `request_id` | Resolve that request |
| `progress` | Optional resolved `request_id` | Root-agent progress; remaining requests stay pending |
| `turn_ended` | `outcome`: response/failed/interrupted; optional `background`, `provisional` booleans | Response/error availability or interruption |
| `session_ended` | None | Clear attention on exit |

Send one JSON object to `tmux-attention report`, containing `version: 1`, `event`,
and opaque `session_id`, plus the event fields above. Request reasons are `approval`,
`question`, `plan`, or `elicitation`. Conversation/turn/request IDs are bounded and
never displayed; prompts, tool arguments/output and transcripts are discarded.
The shared reducer accepts normalized metadata independently of native hook names.
Further harnesses still need an explicit launcher/identity adapter; no OpenCode,
Gemini or other adapter is installed. Reports require the managed launch record,
invocation nonce, tmux server, pane and original pane PID. Stale sessions/turns,
replaced invocations and child-agent hook payloads are rejected.

Signals describe the last observed state. Stop hooks precede final continuation
decisions: response alerts are provisional and withdraw on later root progress.
Stop alone does not resolve pending input; matching request resolution or a new
turn/session must supersede it.
Claude background tasks suppress ready; scheduled crons do not imply active work.
Permission hooks precede the user's decision, sometimes even an automatic policy
decision. Resolution arrives at tool completion, so an approval may remain shown
while its command runs; simultaneous same-tool approvals coalesce when native
payloads lack request IDs. Claude questions/plans use Pre/PostToolUse, elicitation
uses its native request/result hooks, and terminal failures use StopFailure.
Tool failures themselves can be recoverable and do not create error alerts.
Delayed Claude permission/elicitation notifications are fallbacks; idle/auth and
teammate notifications are ignored. Claude lacks our native interruption signal.
Codex question/permission tools are translated only when its local-tool hook path
emits them; specialized paths can bypass it. Asynchronous questions need a separate
answer signal and are not inferred from tool completion. Child input routing,
background completion and silent API failure coverage remain incomplete.

Run `python3 scripts/verify-attention.py` for our reducer, guards, additive setup,
concurrent events, linked-window counts and real fzf/tmux navigation with synthetic
agents and two isolated clients. It does not claim native-harness delivery or
physical-terminal verification. Use the recovery, task and review checks after
changes to their shared helpers; no live session or provider is needed by the suite.

## Review and shortcut verification

The private review wrapper currently requires Linux XDG storage. macOS tuicr uses
Library/Application Support; implement/verify isolation there before applying the
wrapper (plain `tuicr -w` is available). Preserve HOME/Git ignore settings; changing
HOME can silently change which files get reviewed.

Resolve the latest stable [tuicr release](https://github.com/agavra/tuicr/releases/latest)
at installation; verify the official asset digest before placing a versioned binary
and command link on PATH. Apply its config, `tmux-review`, the other helpers,
`tmux_keys.py`, and generated cheatsheet together. The managed editor command
`tmux-review --edit` restores normal HOME/XDG settings before opening Neovim.

For key changes, run `python3 scripts/sync-tmux-keys.py`, then its `--check` mode.
Do not edit the generated block/sheet directly. CI checks generation with Python alone;
private tmux overrides/plugins can add or replace bindings and need a machine check.
Review ergonomics, terminal collisions, and selected-task identity when adding keys.
Task actions use Alt+s (shell), Ctrl+R (review), Alt+n (name), Alt+b (previous),
Alt+a/Alt+h (hide/show), and Ctrl+L (refresh); ordinary query editing stays available.

Run `python3 scripts/verify-reviews.py` with installed tuicr, or `--tuicr /path/to/tuicr`
for a temporary binary. The Linux fake-agent fixture exercises real tuicr, private
exports/comments, revision isolation, ID/revision refusal, Neovim environment,
no-Enter preparation, and narrow/wide terminals. Also run tmux/task checks and
scoped chezmoi preview/dry-run/reruns/restoration. Verify real agent input deliberately;
these checks never send feedback to a real conversation. Actual SSH clipboard is separate.

## Shell verification

Check the managed sources with `zsh -n home/dot_zshenv` and
`zsh -n home/dot_zshrc`. Preview/apply only these targets in an isolated home,
with separate ZDOTDIR and XDG config/data/state/cache directories. Check dry-run,
repeated apply, private overrides, and restoration of a backed-up conflict.
Verify quiet non-interactive commands, Vim editing, completion, shared history,
suggestion acceptance, and fuzzy shortcuts in disposable terminal sessions.
Measure first and repeated prompt readiness, first completion/navigation, and idle
resource use with representative history/project sizes. Keep detailed pilot checks
and machine-specific results outside Git; permanent plugin tests are unnecessary.

## Editor verification

Use isolated HOME and XDG config/data/state/cache directories. Load the managed
configuration headlessly, then check browsing, project search/quickfix, filetype and
EditorConfig indentation, undo across restarts, local overrides, and external edits.
Check scoped chezmoi preview/dry-run/reruns and backup/restoration there first.
Use disposable projects to check actual LSP diagnostics/navigation/completion for
the configured languages, Markdown fences, Mermaid filetypes, manual formatting,
and on-demand plugin shortcuts. Verify first installation creates missing parents
and that cheatsheet/config keys work after generating help tags. Check missing
dependencies leave native editing usable; keep installs out of checks.
Use disposable terminals for split keys and normal/visual clipboard mappings;
capture OSC 52 output without forwarding it to a real clipboard. Measure first paint,
first navigation/search/plugin use, and idle CPU/memory against a clean baseline.
Measure language-server first-use and resources separately from editor paint; Java
and project indexing can be materially heavier. Keep detailed checks/results
privately; configuration changes need no permanent upstream-plugin harness.
