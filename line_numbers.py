"""A line-number gutter that stays in sync with the editor.

This is a thin Canvas drawn to the left of the text area. Rather than trying to
mirror the text's scroll position with arithmetic, we ask the Text widget
itself where each visible line is drawn (``dlineinfo``) and paint the matching
number at the same vertical position. That keeps the numbers perfectly aligned
through scrolling, wrapping, and font changes with almost no bookkeeping.

The gutter redraws whenever the text emits ``<<TextModified>>`` (see
``code_text.py``) or when it is resized.
"""

import tkinter as tk

import config


class LineNumbers(tk.Canvas):
    """A gutter Canvas that paints line numbers beside a CodeText widget."""

    def __init__(self, master, text_widget):
        super().__init__(
            master,
            width=config.GUTTER_WIDTH,
            background=config.GUTTER_BG,
            highlightthickness=0,  # No focus border around the canvas.
        )
        self.text = text_widget

        # Redraw when the text changes, scrolls, or we are resized.
        self.text.bind("<<TextModified>>", self._on_change, add="+")
        self.text.bind("<<TextScrolled>>", self._on_change, add="+")
        self.bind("<Configure>", self._on_change, add="+")

    def _on_change(self, event=None):
        self.redraw()

    def redraw(self):
        """Repaint every currently visible line number."""
        self.delete("all")

        # Walk from the first visible line downwards. `dlineinfo` returns the
        # on-screen geometry of a line, or None once we scroll past the bottom
        # of the visible area -- which is our signal to stop.
        index = self.text.index("@0,0")
        while True:
            line_geometry = self.text.dlineinfo(index)
            if line_geometry is None:
                break

            y = line_geometry[1]  # Pixel y-position of this line in the widget.
            line_number = index.split(".")[0]
            self.create_text(
                config.GUTTER_WIDTH - 6,
                y,
                anchor="ne",  # Right-align the numbers against the text.
                text=line_number,
                fill=config.GUTTER_FG,
                font=config.FONT,
            )
            index = self.text.index(index + "+1line")
