"""Central configuration for the editor.

Everything a user is likely to want to tweak lives here so the rest of the
code can stay focused on behaviour rather than magic numbers. Nothing in this
file talks to Tkinter or Ollama directly; it is plain data.
"""

# --- Ollama connection -------------------------------------------------------

# Base URL of the local Ollama server. Ollama listens here by default.
OLLAMA_URL = "http://localhost:11434"

# Which locally-installed model to ask for completions. Run `ollama list` to
# see what you have pulled. A small, fast model gives the snappiest typing
# experience; a larger one gives better suggestions at the cost of latency.
MODEL = "qwen2.5-coder:1.5b"


# --- Language ----------------------------------------------------------------

# The programming language the editor assumes you are writing. For now the
# editor supports exactly one language; naming it here lets us tell the model
# what to complete and show it to the user. `name` is what the model is told;
# `label` is what the status bar shows.
LANGUAGE_NAME = "Python 3"
LANGUAGE_LABEL = "Python 3"


# --- Editing behaviour -------------------------------------------------------

# One indent level, in spaces. Python's convention is 4 spaces, and the editor
# inserts spaces (never literal tab characters) so files stay consistent.
INDENT_SPACES = 4
INDENT = " " * INDENT_SPACES


# --- Completion behaviour ----------------------------------------------------

# How long to wait after the last keystroke before asking the model for a
# suggestion, in milliseconds. This "debounce" avoids firing a request on every
# single character while the user is typing quickly.
DEBOUNCE_MS = 400

# How many characters of code *before* the cursor to send as context. We cap
# this so the prompt stays small (and therefore fast) even in a large file.
CONTEXT_CHARS = 2000

# Sampling temperature for the model. Low values keep completions predictable
# and on-topic, which is what you want for code.
TEMPERATURE = 0.2

# Upper bound on how many tokens the model may generate for one suggestion.
# We only ever want a single line, so this stays small.
MAX_TOKENS = 64

# How long to wait for the whole HTTP request before giving up, in seconds.
REQUEST_TIMEOUT = 20

# Fill-in-the-middle (FIM) tokens for the completion model. Code models are
# trained to fill the gap between a prefix (code before the cursor) and a suffix
# (code after it), with the gap marked by these special tokens. The values below
# are Qwen2.5-Coder's; a different model family may use different tokens, so
# change these if you change MODEL. STOP_TOKENS end a suggestion -- the newline
# keeps us to a single line, and the rest stop the model running past its answer.
FIM_PREFIX = "<|fim_prefix|>"
FIM_SUFFIX = "<|fim_suffix|>"
FIM_MIDDLE = "<|fim_middle|>"
STOP_TOKENS = ["\n", "<|endoftext|>", "<|fim_pad|>", "<|file_sep|>", "<|repo_name|>"]


# --- Appearance --------------------------------------------------------------

FONT = ("Menlo", 14)          # Any monospace font installed on the system.
EDITOR_BG = "#1e1e1e"
EDITOR_FG = "#d4d4d4"
CURSOR_COLOR = "#d4d4d4"
GHOST_COLOR = "#6a6a6a"       # Colour of the inline suggestion (ghost text).

# Syntax highlighting colours, keyed by the category names the highlighter uses.
SYNTAX_COLORS = {
    "keyword": "#569cd6",     # if, for, def, return, ...
    "string": "#ce9178",      # "text", 'text', f"..."
    "comment": "#6a9955",     # # comments
    "number": "#b5cea8",      # 42, 3.14, 0xff
    "builtin": "#4ec9b0",     # print, len, range, ...
    "definition": "#dcdcaa",  # the name right after `def` or `class`
}

# How long to wait after an edit before re-highlighting, in milliseconds. Like
# the completion debounce, this coalesces bursts of typing into one repaint.
HIGHLIGHT_DELAY_MS = 60

# Shown at the front of the window title while there are unsaved changes.
MODIFIED_INDICATOR = "● "  # ●

STATUS_BG = "#252526"         # Background of the status bar along the bottom.
STATUS_FG = "#9d9d9d"

GUTTER_BG = "#252526"         # Background of the line-number gutter.
GUTTER_FG = "#6a6a6a"         # Colour of the line numbers themselves.
GUTTER_WIDTH = 52             # Width of the gutter in pixels.

OUTPUT_BG = "#141414"         # Background of the Run output panel.
OUTPUT_FG = "#cfcfcf"
OUTPUT_HEIGHT = 8             # Height of the output panel, in text rows.

TOOLBAR_BG = "#333333"        # Background of the top toolbar.

WINDOW_TITLE = "local_auto_ide"
WINDOW_SIZE = "900x650"
