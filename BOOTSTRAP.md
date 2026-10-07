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
| Workspace/scratch helpers | Python 3.8+ with curses, tmux, Git | Launcher UI and scratch-folder safety; apply the tmux configuration and all five helpers plus `tmux_keys.py` together |
| Agent launching/recovery | Selected Codex and/or Claude Code CLI with SessionStart hooks; tmux-resurrect for layouts | Available in tmux's PATH; exact IDs and credentials stay private |
| Fuzzy selection | fzf | Shell history/file/directory selection, zoxide's `zi`, tmux folder/task pickers, and the full tmux verification suite |
| Local reviews | tuicr, Neovim (`nvim`), Git, less | Private local comments/export and guarded feedback preparation; the editor wrapper keeps normal Neovim paths |
| Interactive shell | Current stable Zsh, zsh-autosuggestions, zsh-syntax-highlighting; fzf integration; fd/fdfind when available | Native Vim editing/completion/history, suggestions/highlighting, on-demand fuzzy navigation |
| CLI essentials | bat, fd, ripgrep, zoxide, delta, Neovim | Read files, find code, jump directories, inspect diffs, edit |
| JSON inspection | jq | Inspect and transform structured CLI output; reuse a suitable existing installation |
| Resource inspection | htop | Inspect agent/process CPU and memory on demand; reuse a suitable existing installation |
| Future navigation/editor work | Neovim configuration, task worktrees/resource associations | Broader navigation/editor work remains planned |

Managed helper sources are `home/dot_local/bin/executable_tmux-workspace`,
`executable_tmux-scratch`, `executable_tmux-agent`, `executable_tmux-tasks`, and `executable_tmux-review`
with the shared `tmux_keys.py` catalog. Chezmoi's [`executable_` attribute](https://www.chezmoi.io/reference/source-state-attributes/)
marks executable permissions; the installed commands are `~/.local/bin/tmux-workspace`
`~/.local/bin/tmux-scratch`, `~/.local/bin/tmux-agent`, `~/.local/bin/tmux-tasks`, and `~/.local/bin/tmux-review`.
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

## Agent recovery setup

Apply the tmux configuration and all five helpers plus `tmux_keys.py` together. Install tmux-resurrect
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
