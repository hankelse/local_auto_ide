# local_auto_ide

A bare-bones text editor that autocompletes lines as you type, using a local
LLM served by [Ollama](https://ollama.com). Everything runs on your machine —
no cloud, no API keys, no third-party Python packages.

## How it works

As you type, the editor waits for a brief pause, sends the code around your
cursor to Ollama, and shows the model's completion of the current line inline
in grey ("ghost text").

- **Tab** — accept the suggestion (or, with none showing, insert a 4-space indent)
- **Esc** — dismiss it
- **keep typing** — replace it

If Ollama isn't running, the editor still works as a plain text editor;
suggestions just won't appear.

Other features:

- **Multiple files in tabs** — open several files at once; New / Open / Close
  Tab buttons, or ⌘N / ⌘O / ⌘W. Each tab tracks its own unsaved changes.
- **Syntax highlighting** for Python (keywords, strings, comments, numbers,
  built-ins, and `def`/`class` names).
- **Unsaved-changes indicator**: a ● appears in the title bar while the buffer
  has edits you haven't saved.
- **Line numbers** in a gutter down the left.
- **Smart indent**: pressing Return keeps the current line's indentation and
  adds one level after a line ending in `:`.
- **Open / Save / Save As** for `.py` files (buttons, or ⌘O / ⌘S).
- **Run ▶** executes the current buffer and streams its output to the panel at
  the bottom (button, or ⌘R). It runs what's on screen even if you haven't
  saved, so you can try code freely.
- **Save-on-close prompt**: closing the window with unsaved changes asks whether
  to save first.

Only **Python 3** is supported for now. The active language is shown in the
status bar at the bottom of the window.

### Completion model

Completions use a **fill-in-the-middle (FIM)** code model — `qwen2.5-coder:1.5b`
by default — which is far better at continuing code than a general chat model.
The model and its FIM tokens are set in `config.py`; if you swap in a different
model family, update the `FIM_*` and `STOP_TOKENS` values to match it.

## Requirements

1. **Ollama**, running locally with the completion model pulled:
   ```bash
   ollama pull qwen2.5-coder:1.5b
   ollama serve            # usually already running after install
   ```
2. **A Python with a modern Tkinter (Tcl/Tk 8.6+).** macOS's built-in Python
   uses Apple's old Tcl/Tk 8.5, which renders the editor incorrectly (typed
   text may not appear). Use a Homebrew Python with `python-tk` instead — the
   one-time setup below does this.

## Setup (one time)

```bash
brew install python-tk@3.14          # modern Tcl/Tk + the tkinter binding
python3.14 -m venv venv              # create the project's virtual environment
```

## Run

```bash
./run.sh
```

(equivalently `./venv/bin/python main.py`).

## Layout

The code is split into small, single-purpose modules:

| File               | Responsibility                                              |
| ------------------ | ----------------------------------------------------------- |
| `config.py`        | All tunable settings (model, timing, colours, FIM tokens).  |
| `ollama_client.py` | Talking to Ollama (fill-in-the-middle) and cleaning output. |
| `code_text.py`     | A Text widget that reports content and scroll changes.      |
| `highlighter.py`   | Python syntax highlighting via the `tokenize` module.       |
| `line_numbers.py`  | The line-number gutter.                                     |
| `runner.py`        | Running the file as a subprocess and streaming its output.  |
| `editor_tab.py`    | One open file: text, autocomplete, highlighting, save state.|
| `editor.py`        | The window shell: tab bar, toolbar, output panel, Run.      |
| `main.py`          | Entry point.                                                |

Development ideas and progress are tracked in [`ROADMAP.md`](ROADMAP.md).

## Configuration

Open `config.py` to change the model, the typing pause before a request
(`DEBOUNCE_MS`), how much context is sent (`CONTEXT_CHARS`), or the colours.
A larger model gives better suggestions but responds more slowly.

## Notes and limitations

This is a deliberately minimal foundation. There is no multi-line completion,
the unsaved-changes indicator doesn't notice when an undo returns the buffer to
its saved state, and Run always uses this project's own Python interpreter (the
venv), so scripts that need extra packages won't find them. Running an unsaved
buffer executes it from a temporary file, so `__file__` and paths relative to
the script point at that temp location until you save. Suggestion quality
is bound by the local model; a larger code model gives better completions at the
cost of latency.
