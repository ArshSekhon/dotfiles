"""One catalog for native tmux bindings, popup actions, and generated help.
Run python3 scripts/sync-tmux-keys.py after changing this file.
No downloads, installs, or work at idle.
"""

PREFIX = (
    ('prefix', 'C-a', 'Send Ctrl+A to the application', 'bind C-a send-prefix'),
    ('copy-mode-vi', 'v', 'Select in copy mode', 'bind -T copy-mode-vi v send-keys -X begin-selection'),
    ('copy-mode-vi', 'y', 'Copy to device clipboard; exit', 'bind -T copy-mode-vi y send-keys -X copy-selection-and-cancel'),
    ('prefix', 'c', 'New shell window in the current folder', 'bind c new-window -c "#{pane_current_path}"'),
    ('prefix', '|', 'Shell split: side by side', 'bind | split-window -h -c "#{pane_current_path}"'),
    ('prefix', '-', 'Shell split: top and bottom', 'bind - split-window -v -c "#{pane_current_path}"'),
    ('prefix', 'h', 'Move left', 'bind h select-pane -L'),
    ('prefix', 'j', 'Move down', 'bind j select-pane -D'),
    ('prefix', 'k', 'Move up', 'bind k select-pane -U'),
    ('prefix', 'l', 'Move right', 'bind l select-pane -R'),
    ('prefix', 'H', 'Resize left', 'bind -r H resize-pane -L 5'),
    ('prefix', 'J', 'Resize down', 'bind -r J resize-pane -D 5'),
    ('prefix', 'K', 'Resize up', 'bind -r K resize-pane -U 5'),
    ('prefix', 'L', 'Resize right', 'bind -r L resize-pane -R 5'),
    ('prefix', 'Tab', 'Previous window', 'bind Tab last-window'),
    ('prefix', 's', 'Session picker', 'bind s choose-tree -Zs'),
    ('prefix', 'w', 'Window picker', 'bind w choose-tree -Zw'),
    ('prefix', 'R', 'Reload configuration', 'bind R source-file ~/.tmux.conf \\; display-message "tmux reloaded"'),
    ('prefix', '?', 'Shortcut cheatsheet', 'bind ? display-popup -EE -w 85% -h 85% -T \'Keys\' \'exec env LESS= LESSOPEN= LESSCLOSE= LESSHISTFILE=- LESSSECURE=1 less -i -P"j/k scroll  / search  q close" "$HOME/.config/tmux/cheatsheet.txt"\''),
    ('prefix', 'N', 'Workspace: launch an agent or scratch task', 'bind N run-shell -C "display-popup -EE -w 64 -h 13 -T \'Workspace\' -e DOTFILES_TMUX_CLIENT=#{q:client_name} -e DOTFILES_TMUX_SOCKET=#{q:socket_path} -e DOTFILES_TMUX_PANE=#{pane_id} \'exec \\"\\$HOME/.local/bin/tmux-workspace\\" --menu\'"'),
    ('prefix', 'b', 'Previous session', 'bind b switch-client -l'),
    ('prefix', 'g', 'Find existing tasks, agents and panes', 'bind g run-shell -C "display-popup -EE -w 90% -h 80% -T \'Tasks\' -e DOTFILES_TMUX_CLIENT=#{q:client_name} -e DOTFILES_TMUX_SOCKET=#{q:socket_path} \'exec \\"\\$HOME/.local/bin/tmux-tasks\\"\'"'),
    ('prefix', 'B', 'Previous task', 'bind B run-shell \'DOTFILES_TMUX_CLIENT=#{q:client_name} DOTFILES_TMUX_SOCKET=#{q:socket_path} exec "$HOME/.local/bin/tmux-tasks" --previous\''),
    ('prefix', 'r', 'Review current task; save private feedback', 'bind r run-shell -C "display-popup -EE -w 95% -h 90% -T \'Local review\' -e DOTFILES_TMUX_CLIENT=#{q:client_name} -e DOTFILES_TMUX_SOCKET=#{q:socket_path} -e DOTFILES_TMUX_PANE=#{pane_id} \'exec \\"\\$HOME/.local/bin/tmux-review\\"\'"'),
    ('prefix', 'z', 'Toggle pane zoom', 'bind z resize-pane -Z'),
    ('prefix', '[', 'Enter copy mode', 'bind [ copy-mode'),
)

# Key -> (action token, label). Tokens are independent of chosen keys.
TASK_ACTIONS = {
    "enter": ("jump", "jump"),
    "alt-s": ("shell", "shell"),
    "ctrl-r": ("review", "review"),
    "alt-n": ("rename", "name"),
    "alt-a": ("hide", "hide/unhide"),
    "alt-h": ("hidden", "show hidden"),
    "ctrl-l": ("refresh", "refresh"),
    "alt-b": ("previous", "previous task"),
}
FOLDER_ACTIONS = {
    "enter": ("choose", "choose"),
    "tab": ("browse", "browse one level"),
    "alt-h": ("parent", "parent folder"),
}
WORKSPACE_ACTIONS = {
    "t": ("scratch", "Scratch task (private folder)", "scratch"),
    "p": ("pane", "New agent pane (current folder)", "pane"),
    "P": ("named-pane", "Named agent pane (current folder)", "named pane"),
    "s": ("session", "New session (current folder)", "session"),
    "f": ("folder", "Folder picker", "folder"),
    "g": ("tasks", "Existing work", "existing work"),
}
WORKSPACE_NAVIGATION = {"j": "down", "k": "up", "h": "agent", "l": "agent",
                        "Enter": "open", "Esc": "cancel", "q": "cancel"}
NAME_KEYS = {"Ctrl+U": "clear", "Ctrl+F": "folder", "Enter": "open", "Esc": "back"}
REVIEW_ACTIONS = {"p": ("prepare", "prepare feedback for this agent"),
                  "v": ("view", "view saved feedback"),
                  "r": ("again", "review again"), "q": ("close", "close")}


def key_label(key):
    aliases = {"enter": "Enter", "tab": "Tab", "esc": "Esc", "C-a": "Ctrl+A"}
    if key in aliases:
        return aliases[key]
    if key.startswith("ctrl-"):
        return "Ctrl+" + key[5:].upper()
    if key.startswith("alt-"):
        return "Alt+" + key[4:]
    return key


def action_key(actions, action):
    return next(key for key, value in actions.items() if value[0] == action)


def navigation_key(action):
    return next(key for key, value in WORKSPACE_NAVIGATION.items() if value == action)


def prefix_key(helper):
    return next(key for table, key, _, command in PREFIX
                if table == "prefix" and helper in command and "--previous" not in command)


def action_hint(actions):
    return "  ".join(key_label(key) + " " + (value[2] if len(value) > 2 else value[1])
                     for key, value in actions.items())


def fzf_bindings(actions):
    result = ["ctrl-j:down", "ctrl-k:up"]
    for key, (action, _) in actions.items():
        wait = "+wait" if action not in ("previous", "hidden", "refresh", "parent") else ""
        result.append(key + ":print(" + action + ")" + wait + "+accept")
    if "enter" in actions:
        result.append("double-click:print(" + actions["enter"][0] + ")+wait+accept")
    return ",".join(result)


def workspace_hint():
    names = {"down": "choose", "up": "choose", "agent": "agent",
             "open": "open", "cancel": "cancel"}
    grouped = {}
    for key, action in WORKSPACE_NAVIGATION.items():
        grouped.setdefault(names[action], []).append(key)
    return "  ".join("/".join(keys) + " " + label for label, keys in grouped.items())


def name_hint():
    return "  ".join(key + " " + action for key, action in NAME_KEYS.items() if action != "folder")


def validate():
    from collections import Counter
    import shlex
    for table, key, _, command in PREFIX:
        fields = shlex.split(command.replace("\\\n", " "))
        actual_table = fields[2] if fields[1] == "-T" else "prefix"
        index = 3 if fields[1] == "-T" else 2 if fields[1] == "-r" else 1
        if actual_table != table or fields[index] != key:
            raise ValueError("Binding/catalog mismatch: " + command)
    if any(count > 1 for count in Counter((table, key) for table, key, _, _ in PREFIX).values()):
        raise ValueError("Duplicate tmux binding")
    for actions in (TASK_ACTIONS, FOLDER_ACTIONS):
        if any(key in actions for key in ("ctrl-s", "ctrl-q", "ctrl-j", "ctrl-k")):
            raise ValueError("Picker action conflicts with navigation or flow control")
        if len({action for action, _ in actions.values()}) != len(actions):
            raise ValueError("Duplicate picker action")


def native_bindings():
    validate()
    return "\n".join(command for _, _, _, command in PREFIX) + "\n"


def cheatsheet():
    """Present keys by workflow, with clear prefix/popup boundaries."""
    import textwrap
    validate()
    used = set()

    def binding(label, *commands, table="prefix", previous=False):
        keys = []
        for command in commands:
            matches = [item for item in PREFIX if item[0] == table and command in item[3]
                       and ("--previous" in item[3]) == previous]
            if len(matches) != 1:
                raise ValueError("Ambiguous cheatsheet binding: " + command)
            _, key, _, _ = matches[0]
            used.add((table, key))
            keys.append(key_label(key))
        return (" / ".join(keys), label)

    def actions(catalog, labels):
        return [(key_label(key), labels.get(value[0], value[1]))
                for key, value in catalog.items()]

    def navigation(*tokens):
        return "/".join(key for key, action in WORKSPACE_NAVIGATION.items() if action in tokens)

    def naming(*tokens):
        return "/".join(key for key, action in NAME_KEYS.items() if action in tokens)

    lines = ["TMUX SHORTCUTS", "j/k scroll   / search   q close",
             "Single uppercase keys use Shift: N = Shift+n.", ""]

    def heading(title, note=None):
        lines.extend([title, "-" * 54])
        if note:
            lines.extend(textwrap.wrap(note, width=54, initial_indent="  ", subsequent_indent="  "))

    def rows(items, indent=2):
        for key, label in items:
            column = max(20 - indent, len(key) + 2)
            start = " " * indent + key.ljust(column)
            lines.extend(textwrap.wrap(label, width=54, initial_indent=start,
                                       subsequent_indent=" " * len(start)))

    heading("TMUX  |  Press Ctrl+A, then a key")
    groups = [
        ("Agents & tasks", [
            binding("Launch agent / scratch task", "tmux-workspace"),
            binding("Find tasks and agent panes", "tmux-tasks"),
            binding("Review the current task", "tmux-review"),
        ]),
        ("Switch", [
            binding("Previous task", "tmux-tasks", previous=True),
            binding("Previous session", "switch-client -l"),
            binding("Previous window", "last-window"),
            binding("Session / window picker", "choose-tree -Zs", "choose-tree -Zw"),
        ]),
        ("Windows & panes", [
            binding("New shell window (current folder)", "new-window"),
            binding("Shell split: beside / below", "split-window -h", "split-window -v"),
            binding("Move left / down / up / right", "select-pane -L", "select-pane -D", "select-pane -U", "select-pane -R"),
            binding("Resize left / down / up / right", "resize-pane -L", "resize-pane -D", "resize-pane -U", "resize-pane -R"),
            binding("Zoom / unzoom pane", "resize-pane -Z"),
        ]),
        ("Copy & settings", [
            binding("Copy mode (v selects, y copies)", "copy-mode"),
            binding("This cheatsheet", "cheatsheet.txt"),
            binding("Reload configuration", "source-file"),
            binding("Send Ctrl+A to the application", "send-prefix"),
        ]),
    ]
    for title, items in groups:
        lines.append("  " + title)
        rows(items, indent=4)
        lines.append("")
    extra = [(key_label(key), label) for table, key, label, _ in PREFIX
             if table == "prefix" and (table, key) not in used]
    if extra:
        lines.append("  Other controls")
        rows(extra, indent=4)
        lines.append("")

    heading("WORKSPACE  |  Ctrl+A " + prefix_key("tmux-workspace"),
            "Inside popup: no prefix. Last agent is remembered.")
    rows(actions(WORKSPACE_ACTIONS, {
        "scratch": "Scratch task in a private folder",
        "pane": "New agent pane (current folder)",
        "named-pane": "Named agent pane (current folder)",
        "session": "Named session (current folder)",
        "folder": "Pick a folder for a new session",
        "tasks": "Find existing work",
    }))
    rows([(navigation("down", "up"), "Choose a menu item"),
          (navigation("agent"), "Switch Codex / Claude"),
          (navigation("open"), "Open selected item"),
          (navigation("cancel"), "Back / cancel")])
    lines.append("  While naming (letters enter text):")
    rows([(naming("clear"), "Clear name"),
          (naming("folder"), "Change folder (new session)"),
          (naming("open", "back"), "Open / back")])
    lines.append("")

    heading("TASK SWITCHER  |  Ctrl+A " + prefix_key("tmux-tasks"),
            "Inside popup: type to search; actions use selection.")
    rows([("Ctrl+j/k", "Move through results"), ("Esc", "Cancel")])
    rows(actions(TASK_ACTIONS, {
        "jump": "Jump to selected pane", "shell": "Shell split in its folder",
        "review": "Review selected task", "rename": "Rename pane",
        "hide": "Hide / unhide (keeps running)", "hidden": "Include hidden panes",
        "refresh": "Refresh results", "previous": "Previous task",
    }))
    lines.append("")

    heading("FOLDER PICKER  |  Workspace " + key_label(action_key(WORKSPACE_ACTIONS, "folder")),
            "Type to search, or enter ~, /path, ./path, ../path.")
    rows([("Ctrl+j/k", "Move through results"), ("Esc", "Back")])
    rows(actions(FOLDER_ACTIONS, {"choose": "Choose folder", "browse": "Browse one level",
                                "parent": "Parent folder"}))
    lines.append("")

    heading("LOCAL REVIEW  |  Ctrl+A " + prefix_key("tmux-review"),
            "Inside Tuicr: comments stay private.")
    rows([("?", "Tuicr help"), ("c / C", "Line / file comment"),
          ("v then c", "Range comment"), ("Tab / ;l", "Next panel / focus diff on right"),
          ("Enter", "Save comment"), ("Ctrl+j", "Newline in comment"),
          ("ZZ", "Export; open feedback actions"), (":q", "Exit without exporting")])
    lines.append("")

    heading("FEEDBACK  |  After exporting with ZZ")
    rows(actions(REVIEW_ACTIONS, {"prepare": "Prepare prompt in the exact agent",
                                "view": "View saved feedback", "again": "Review again", "close": "Close"}))
    rows([("Enter (agent)", "Send prepared prompt when ready")])
    lines.extend(["  Prepare checks the conversation and Git revision.", ""])

    heading("COPY MODE  |  After Ctrl+A " + next(key_label(key) for table, key, _, command in PREFIX
                                               if table == "prefix" and command.endswith(" copy-mode")))
    rows([(key_label(key), label) for table, key, label, _ in PREFIX if table == "copy-mode-vi"])
    return "\n".join(lines) + "\n"
