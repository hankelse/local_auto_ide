"""One open file: its text area, autocomplete, highlighting, and edit state.

Each tab in the editor is an `EditorTab`. It owns everything specific to a
single file -- the text widget and its line-number gutter, the syntax
highlighter, the file path, the unsaved-changes flag, and the inline AI
suggestion currently on screen. The surrounding app (`Editor`) owns the things
shared across files: the toolbar, the tab bar, the output panel, and Run.

When a tab's displayed state changes (its file path or unsaved-changes flag),
it calls the `on_state_change` callback it was given, so the app can refresh
that tab's label and the window title.

Two implementation details carried over from the single-file design:

1. Ghost text vs. real text.
   The suggestion is inserted into the text widget as normal characters, tagged
   "ghost" so it renders grey and bracketed by two marks
   ("ghost_start"/"ghost_end") so we always know which range it is. The caret is
   parked at ghost_start, so the grey text sits to its right. Accepting drops
   the grey tag; dismissing deletes the range.

2. Keeping the UI responsive.
   Talking to the model is slow and Tkinter is single-threaded, so each
   completion runs on a background thread that touches no widgets and only feeds
   its result into a thread-safe queue. The tab polls that queue on a timer and
   displays results on the main thread.
"""

import queue
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog

import config
import ollama_client
from code_text import CodeText
from highlighter import Highlighter
from line_numbers import LineNumbers


# Key presses that only change modifiers (Shift, Ctrl, ...) should not count as
# "the user typed something", so we ignore them when deciding whether to clear a
# suggestion or ask for a new one.
_MODIFIER_KEYSYMS = {
    "Shift_L", "Shift_R", "Control_L", "Control_R",
    "Alt_L", "Alt_R", "Meta_L", "Meta_R", "Caps_Lock",
}


class EditorTab:
    """The editing surface and state for a single open file."""

    def __init__(self, master, on_state_change):
        # `frame` is what the app adds to the tab bar; everything else lives
        # inside it.
        self.frame = tk.Frame(master)
        self._on_state_change = on_state_change

        # Path of the file in this tab, or None for a never-saved buffer.
        self.filepath = None

        # Whether this buffer has unsaved changes. `_suppress_modified` lets us
        # make edits (inserting/removing ghost text) that must NOT count as user
        # changes, so the "modified" dot only reflects real editing.
        self.modified = False
        self._suppress_modified = False

        # While False, pending timers stop rescheduling -- used so a closed tab
        # doesn't keep polling after its widgets are gone.
        self._alive = True

        # --- Suggestion state ---
        self.suggestion = ""            # Grey text on screen, or "" if none.
        self._debounce_handle = None    # Pending debounce timer, or None.
        self._latest_request_id = 0     # Newest completion request id.
        self._results = queue.Queue()   # Completions from the worker thread.

        self._build_editing_area()
        self._bind_events()
        self._poll_results()

    # -- Widget setup ---------------------------------------------------------

    def _build_editing_area(self):
        """Create the gutter + text widget + scrollbar inside this tab's frame."""
        self.text = CodeText(
            self.frame,
            wrap="none",
            undo=True,  # Free Ctrl/Cmd-Z support from the widget itself.
            font=config.FONT,
            background=config.EDITOR_BG,
            foreground=config.EDITOR_FG,
            insertbackground=config.CURSOR_COLOR,
            borderwidth=0,
            padx=8,
            pady=8,
        )
        # The "ghost" tag is what makes suggestion text render grey.
        self.text.tag_configure("ghost", foreground=config.GHOST_COLOR)

        # Syntax highlighting recolours the buffer as it changes. Raising the
        # ghost tag above the syntax tags keeps a suggestion grey even where it
        # overlaps highlighted code.
        self.highlighter = Highlighter(self.text)
        self.text.tag_raise("ghost")

        # Make a literal tab character display as INDENT_SPACES wide, so any
        # tabs in opened files line up with our space-based indentation.
        space_width = tkfont.Font(font=config.FONT).measure(" ")
        self.text.configure(tabs=(space_width * config.INDENT_SPACES,))

        gutter = LineNumbers(self.frame, self.text)
        scrollbar = tk.Scrollbar(self.frame, command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)

        # Order across the frame: gutter | text (expands) | scrollbar.
        gutter.pack(side="left", fill="y")
        scrollbar.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)

    def _bind_events(self):
        """Wire keyboard and mouse events to their handlers.

        Returning "break" from a handler tells Tkinter to stop processing the
        event, which is how we override the default meaning of keys like Tab,
        Return, and Escape.
        """
        self.text.bind("<Key>", self._on_key)
        self.text.bind("<KeyRelease>", self._on_key_release)
        self.text.bind("<Tab>", self._on_tab)
        self.text.bind("<Return>", self._on_return)
        self.text.bind("<Escape>", self._on_escape)
        self.text.bind("<Button-1>", lambda event: self.clear_suggestion())

        # Tk sets an internal "modified" flag and fires <<Modified>> whenever the
        # text content changes; we use it to drive the unsaved-changes indicator.
        self.text.bind("<<Modified>>", self._on_text_modified)

    # -- Public API used by the app -------------------------------------------

    def load(self, path):
        """Replace this tab's contents with the file at `path`."""
        with open(path, "r") as handle:
            contents = handle.read()

        self.clear_suggestion()
        self.text.delete("1.0", "end")
        self.text.insert("1.0", contents)
        self.text.edit_reset()      # A freshly opened file has no undo history.
        self.text.mark_set("insert", "1.0")
        self.filepath = path
        self._mark_saved()          # A just-opened file has no unsaved changes.
        self.highlighter.highlight()
        self._notify_state_change()

    def save(self):
        """Save to the current file, prompting for a path if there isn't one.

        Returns True if the file was saved, False if the user cancelled.
        """
        if self.filepath is None:
            return self.save_as()
        self._write_to(self.filepath)
        return True

    def save_as(self):
        """Prompt for a path and save there. Returns True unless cancelled."""
        path = filedialog.asksaveasfilename(
            defaultextension=".py",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")],
        )
        if not path:
            return False  # User cancelled the dialog.
        self._write_to(path)
        self.filepath = path
        self._notify_state_change()
        return True

    def get_contents(self):
        """Return the buffer's text, excluding any grey suggestion."""
        self.clear_suggestion()
        # "end-1c" trims the trailing newline Tkinter always keeps at the end.
        return self.text.get("1.0", "end-1c")

    def title_label(self):
        """The tab's label: filename (or 'untitled'), with a ● when modified."""
        name = _basename(self.filepath) if self.filepath else "untitled"
        indicator = config.MODIFIED_INDICATOR if self.modified else ""
        return indicator + name

    def display_name(self):
        """A friendly name for this file, used in the Run output header."""
        return _basename(self.filepath) if self.filepath else "untitled"

    def is_blank(self):
        """True if this tab is an untitled buffer with no edits (safe to reuse)."""
        empty = self.text.get("1.0", "end-1c") == ""
        return self.filepath is None and not self.modified and empty

    def has_unsaved_changes(self):
        return self.modified

    def focus(self):
        self.text.focus_set()

    def close(self):
        """Stop this tab's timers and destroy its widgets."""
        self._alive = False
        if self._debounce_handle is not None:
            self.text.after_cancel(self._debounce_handle)
        self.frame.destroy()

    # -- Keyboard: suggestions and indentation --------------------------------

    def _on_key(self, event):
        """Runs before a key is inserted. Clears any stale suggestion."""
        if event.keysym in ("Tab", "Return", "Escape"):
            return None
        if event.keysym in _MODIFIER_KEYSYMS:
            return None
        self.clear_suggestion()
        return None

    def _on_key_release(self, event):
        """Runs after a key is inserted. Schedules a new completion request."""
        if event.keysym in ("Tab", "Escape") or event.keysym in _MODIFIER_KEYSYMS:
            return
        self._schedule_completion()

    def _on_tab(self, event):
        """Tab accepts a visible suggestion, or inserts one indent level."""
        if self.suggestion:
            self._accept_suggestion()
        else:
            self.text.insert("insert", config.INDENT)
        return "break"  # Never insert a literal tab character.

    def _on_return(self, event):
        """Return inserts a newline that keeps (and, after ':', grows) indent."""
        self.clear_suggestion()

        line_start = self.text.index("insert linestart")
        line_so_far = self.text.get(line_start, "insert")

        existing_indent = line_so_far[: len(line_so_far) - len(line_so_far.lstrip())]
        new_indent = existing_indent
        if line_so_far.rstrip().endswith(":"):
            new_indent += config.INDENT

        self.text.insert("insert", "\n" + new_indent)
        self.text.see("insert")
        return "break"  # Replace the default newline with our indented one.

    def _on_escape(self, event):
        """Escape dismisses a visible suggestion."""
        self.clear_suggestion()
        return "break"

    # -- Unsaved-changes tracking ---------------------------------------------

    def _on_text_modified(self, event):
        """Handle Tk's <<Modified>> event: mark the buffer as edited."""
        if self._suppress_modified:
            return
        if self.text.edit_modified():
            self._set_modified(True)

    def _set_modified(self, value):
        """Update the unsaved-changes flag and refresh labels if it changed."""
        if value == self.modified:
            return
        self.modified = value
        self._notify_state_change()

    def _mark_saved(self):
        """Record that the buffer now matches what is on disk (no changes)."""
        self._set_modified(False)
        # Reset Tk's own flag too, so the next real edit fires <<Modified>>
        # afresh. This assignment doesn't count as a user change.
        self._suppress_modified = True
        self.text.edit_modified(False)
        self._suppress_modified = False

    def _without_marking_modified(self, mutate):
        """Run a text change that should not affect the unsaved-changes flag."""
        self._suppress_modified = True
        try:
            mutate()
        finally:
            # Restore Tk's flag to match our real modified state.
            self.text.edit_modified(self.modified)
            self._suppress_modified = False

    def _notify_state_change(self):
        """Tell the app that this tab's label/title may need refreshing."""
        self._on_state_change(self)

    # -- Suggestion lifecycle -------------------------------------------------

    def _schedule_completion(self):
        """(Re)start the debounce timer that will request a completion."""
        if self._debounce_handle is not None:
            self.text.after_cancel(self._debounce_handle)
        self._debounce_handle = self.text.after(
            config.DEBOUNCE_MS, self._request_completion
        )

    def _request_completion(self):
        """Kick off a background request for a completion at the caret."""
        self._debounce_handle = None

        # Don't suggest while there is a selection or an existing suggestion.
        if self.suggestion or self.text.tag_ranges("sel"):
            return

        prefix, suffix = self._context_around_cursor()
        if not prefix.strip():
            return  # Nothing meaningful to complete yet.

        self._latest_request_id += 1
        request_id = self._latest_request_id

        threading.Thread(
            target=self._fetch_in_background,
            args=(request_id, prefix, suffix),
            daemon=True,
        ).start()

    def _fetch_in_background(self, request_id, prefix, suffix):
        """Worker-thread body: call Ollama and queue the result.

        Runs off the main thread, so it must not touch any Tkinter widget.
        """
        completion = ollama_client.request_completion(prefix, suffix)
        self._results.put((request_id, completion))

    def _poll_results(self):
        """Main-thread timer: show any completed request that is still fresh."""
        try:
            while True:
                request_id, completion = self._results.get_nowait()
                # Ignore stale results: a newer request id means the user has
                # typed again since this one was sent.
                if request_id == self._latest_request_id and completion:
                    self._show_suggestion(completion)
        except queue.Empty:
            pass
        finally:
            if self._alive:
                self.text.after(50, self._poll_results)

    def _show_suggestion(self, text):
        """Insert `text` as grey ghost text just after the caret."""
        if self.suggestion:
            return

        def insert_ghost():
            start = self.text.index("insert")
            self.text.insert(start, text, "ghost")
            end = self.text.index("insert")

            # Bracket the suggestion with marks so we can find it despite later
            # edits. Left gravity keeps the start mark pinned in place.
            self.text.mark_set("ghost_start", start)
            self.text.mark_set("ghost_end", end)
            self.text.mark_gravity("ghost_start", "left")

            # Park the caret before the grey text so it reads as an inline hint.
            self.text.mark_set("insert", "ghost_start")

        # Showing a suggestion is not a user edit, so it must not set the
        # unsaved-changes flag.
        self._without_marking_modified(insert_ghost)
        self.suggestion = text

    def _accept_suggestion(self):
        """Turn the grey suggestion into real text and move the caret past it."""
        if not self.suggestion:
            return
        # Dropping the "ghost" tag promotes grey text to normal text; the
        # characters are already in the widget.
        self.text.tag_remove("ghost", "ghost_start", "ghost_end")
        self.text.mark_set("insert", "ghost_end")
        self.suggestion = ""
        # Accepting a suggestion keeps those characters, so the buffer now has
        # unsaved changes.
        self._set_modified(True)

    def clear_suggestion(self):
        """Remove the grey suggestion from the screen, if one is showing."""
        if not self.suggestion:
            return
        # Removing the grey text is not a user edit either.
        self._without_marking_modified(
            lambda: self.text.delete("ghost_start", "ghost_end")
        )
        self.suggestion = ""

    def _context_around_cursor(self):
        """Return (prefix, suffix): code just before and just after the caret."""
        prefix = self.text.get("1.0", "insert")[-config.CONTEXT_CHARS:]
        suffix = self.text.get("insert", "end-1c")[:config.CONTEXT_CHARS]
        return prefix, suffix

    def _write_to(self, path):
        """Write the buffer's text to `path`, excluding any ghost suggestion."""
        contents = self.get_contents()
        with open(path, "w") as handle:
            handle.write(contents)
        self._mark_saved()


def _basename(path):
    """The file name at the end of a path (kept local to avoid an os import)."""
    return path.replace("\\", "/").rsplit("/", 1)[-1]
