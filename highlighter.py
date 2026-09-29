"""Python syntax highlighting for the editor's Text widget.

We colour the code by tokenising it with Python's own `tokenize` module. Using
the real tokeniser (rather than hand-written regexes) means the highlighting
matches Python's actual grammar -- strings, f-strings, numbers and comments are
categorised exactly as the language sees them.

While you type, the code is often temporarily invalid (an unclosed bracket, a
half-written string). `tokenize` yields tokens up to the point where it can no
longer make sense of the text and then raises; we simply highlight everything
it managed to produce and ignore the error. The result is that already-typed
code stays coloured and the incomplete tail is left plain until it is valid.

Highlighting re-runs on every edit, debounced so a burst of keystrokes causes a
single repaint. It recolours the whole buffer each time, which is easily fast
enough for the file sizes a simple editor deals with and keeps the logic clear.
"""

import builtins
import io
import keyword
import token as token_module
import tokenize

import config


# The set of built-in names (print, len, range, ...). Kept as a set for fast
# membership tests while tokenising.
_BUILTINS = set(dir(builtins))

# f-string pieces became their own token types in Python 3.12. We look them up
# by name with getattr so the code still runs on older versions that lack them.
_FSTRING_TOKENS = {
    getattr(token_module, name)
    for name in ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END")
    if hasattr(token_module, name)
}


class Highlighter:
    """Colours a CodeText widget's Python source as it changes."""

    def __init__(self, text_widget):
        self.text = text_widget
        self._pending = None  # Handle of the pending debounce timer, or None.

        # Register one text tag per colour category.
        for category, colour in config.SYNTAX_COLORS.items():
            self.text.tag_configure(category, foreground=colour)

        # Re-highlight after each content change (not on mere scrolling).
        self.text.bind("<<TextModified>>", self._schedule, add="+")

    def _schedule(self, event=None):
        """Restart the debounce timer that will re-highlight the buffer."""
        if self._pending is not None:
            self.text.after_cancel(self._pending)
        self._pending = self.text.after(config.HIGHLIGHT_DELAY_MS, self.highlight)

    def highlight(self):
        """Recolour the whole buffer from scratch."""
        self._pending = None
        source = self.text.get("1.0", "end-1c")

        self._clear_tags()
        # `previous_name` lets us spot a definition: the NAME token right after
        # `def` or `class` is the thing being defined.
        previous_name = ""
        try:
            for tok in tokenize.generate_tokens(io.StringIO(source).readline):
                category = self._category_for(tok, previous_name)
                if category is not None:
                    self._apply(category, tok)
                if tok.type == tokenize.NAME:
                    previous_name = tok.string
        except (tokenize.TokenError, IndentationError, SyntaxError):
            # The remaining text isn't valid (yet). Whatever we tagged before
            # the error stays; the rest is simply left uncoloured.
            pass

    def _category_for(self, tok, previous_name):
        """Return the colour category for one token, or None to leave it plain."""
        if tok.type == tokenize.COMMENT:
            return "comment"
        if tok.type == tokenize.STRING or tok.type in _FSTRING_TOKENS:
            return "string"
        if tok.type == tokenize.NUMBER:
            return "number"
        if tok.type == tokenize.NAME:
            if keyword.iskeyword(tok.string):
                return "keyword"
            if previous_name in ("def", "class"):
                return "definition"
            if tok.string in _BUILTINS:
                return "builtin"
        return None

    def _apply(self, category, tok):
        """Tag the token's on-screen range with its category.

        `tokenize` reports positions as (row, column) with 1-based rows and
        0-based columns, which is exactly Tkinter's "row.column" index format.
        """
        start_row, start_col = tok.start
        end_row, end_col = tok.end
        self.text.tag_add(
            category,
            "%d.%d" % (start_row, start_col),
            "%d.%d" % (end_row, end_col),
        )

    def _clear_tags(self):
        """Remove every syntax tag from the whole buffer before recolouring."""
        for category in config.SYNTAX_COLORS:
            self.text.tag_remove(category, "1.0", "end")
