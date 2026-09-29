# Roadmap

Features that have proven valuable in other IDEs and are candidates for this
project. As we build, ideas move from **Candidates** to **Completed**. New ideas
get added to **Candidates** as they come up.

## Completed

- **AI line autocomplete** — inline grey "ghost text" from a local Ollama model;
  Tab accepts, Esc dismisses, typing replaces.
- **Fill-in-the-middle code model** — uses `qwen2.5-coder` with FIM prompting for
  code-aware completions (prefix + suffix around the cursor).
- **Syntax highlighting** — Python keywords, strings, comments, numbers,
  built-ins, and definition names, via the `tokenize` module.
- **Line numbers** — a gutter that stays aligned through scrolling.
- **Smart indentation** — Return keeps the current indent and adds a level after
  a line ending in `:`.
- **Spaces for indentation** — one indent = 4 spaces.
- **File open / save / save as** — for `.py` files, with keyboard shortcuts.
- **Run** — execute the current buffer (saved or not) and stream output to a
  panel.
- **Unsaved-changes indicator** — a ● in the title bar (now per-tab).
- **Save-on-close prompt** — closing with unsaved changes offers to save.
- **Multi-file tabs** — open several files at once, each in its own tab.

## Candidates

### Editing
- **Find and replace** — within a file, and across the project.
- **Go to line** — jump to a line number.
- **Auto-close brackets and quotes** — insert the closing character
  automatically.
- **Bracket matching** — highlight the matching bracket under the cursor.
- **Toggle line comment** — comment/uncomment selected lines (e.g. ⌘/).
- **Current-line highlight** — subtly highlight the line the cursor is on.
- **Multiple cursors / column selection.**
- **Indentation guides and whitespace rendering.**

### Navigation & project
- **File tree / explorer sidebar** — browse and open files in a folder.
- **Command palette** — fuzzy-search and run any command.
- **Recent files / session restore** — reopen what was open last time.
- **Split view** — see two files or two parts of one file side by side.

### Language intelligence
- **Linting / diagnostics** — surface errors and warnings (e.g. pyflakes).
- **Non-AI symbol completion** — complete names from the code itself (e.g. jedi).
- **Code formatting** — format on demand or on save (e.g. black).
- **Go to definition / find references.**
- **Multi-language support** — pick the language (and completion behaviour) from
  the file extension.

### AI completion improvements
- **Multi-line / block completion** — suggest more than the current line.
- **Accept part of a suggestion** — accept a word at a time.
- **Per-language model configuration.**

### Running & tooling
- **Integrated terminal.**
- **Stop / re-run controls** for a running program.
- **Git integration** — status, diff, stage, commit.

### Appearance & configuration
- **Theme selection** and a settings UI.
- **Status bar details** — line:column, indentation, encoding.
- **Configurable keyboard shortcuts.**
- **Word-wrap toggle.**
