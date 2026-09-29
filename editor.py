"""The editor window: a tabbed shell around one or more open files.

`Editor` owns the parts of the window shared by every open file -- the toolbar,
the tab bar, the Run output panel, and the status bar -- and a list of
`EditorTab`s, one per open file. Each tab is self-contained (its own text area,
autocomplete, highlighting, and save state); the app simply delegates Open /
Save / Run and window-close handling to whichever tab is active.

Keeping all per-file behaviour in `EditorTab` is what makes tabs simple here:
opening a file is "make another tab", and switching files is just switching
which tab's frame the tab bar shows.
"""

import os
import queue
import sys
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import config
import runner
from editor_tab import EditorTab


class Editor:
    """A tabbed, single-window editor with Ollama-backed line completion."""

    def __init__(self, root):
        self.root = root
        self.root.geometry(config.WINDOW_SIZE)

        # All open tabs, in the same order as the tab bar shows them.
        self.tabs = []

        # A scratch file used to run an unsaved buffer (see run_file). Created on
        # first use and reused for the rest of the session.
        self._scratch_path = None

        # Build the UI from the outside in: bars that claim an edge first, then
        # the tab area fills whatever space is left.
        self._build_toolbar()
        self._build_status_bar()
        self._build_output_panel()
        self._build_tabs()

        self._bind_shortcuts()
        # Intercept the window's close button so we can offer to save first.
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.new_tab()  # Start with one empty buffer.

    # -- Widget setup ---------------------------------------------------------

    def _build_toolbar(self):
        """Create the top toolbar with the file and run buttons."""
        toolbar = tk.Frame(self.root, background=config.TOOLBAR_BG)
        toolbar.pack(side="top", fill="x")

        def add_button(label, command):
            tk.Button(toolbar, text=label, command=command).pack(
                side="left", padx=4, pady=4
            )

        add_button("New", self.new_tab)
        add_button("Open", self.open_file)
        add_button("Save", self.save_file)
        add_button("Save As", self.save_file_as)
        add_button("Close Tab", self.close_current_tab)
        add_button("Run ▶", self.run_file)  # ▶

    def _build_status_bar(self):
        """Create the thin bar along the bottom showing the active language."""
        self.status = tk.Label(
            self.root,
            text=config.LANGUAGE_LABEL,
            anchor="w",
            background=config.STATUS_BG,
            foreground=config.STATUS_FG,
            font=config.FONT,
            padx=8,
            pady=2,
        )
        self.status.pack(side="bottom", fill="x")

    def _build_output_panel(self):
        """Create the read-only panel that shows Run output, above the status."""
        frame = tk.Frame(self.root, background=config.OUTPUT_BG)
        frame.pack(side="bottom", fill="x")

        tk.Label(
            frame,
            text="Output",
            anchor="w",
            background=config.OUTPUT_BG,
            foreground=config.OUTPUT_FG,
            font=config.FONT,
            padx=6,
        ).pack(side="top", fill="x")

        self.output = tk.Text(
            frame,
            height=config.OUTPUT_HEIGHT,
            wrap="none",
            font=config.FONT,
            background=config.OUTPUT_BG,
            foreground=config.OUTPUT_FG,
            borderwidth=0,
            padx=6,
            pady=4,
            state="disabled",  # Read-only; we toggle this when writing.
        )
        self.output.pack(side="bottom", fill="both")

    def _build_tabs(self):
        """Create the tab bar (a ttk.Notebook) that fills the remaining space."""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(side="top", fill="both", expand=True)
        # Update the window title and move focus when the user switches tabs.
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _bind_shortcuts(self):
        """Bind common editor shortcuts, for both macOS (⌘) and others (Ctrl)."""
        for modifier in ("Command", "Control"):
            self.root.bind("<%s-n>" % modifier, lambda e: self.new_tab())
            self.root.bind("<%s-o>" % modifier, lambda e: self.open_file())
            self.root.bind("<%s-s>" % modifier, lambda e: self.save_file())
            self.root.bind("<%s-r>" % modifier, lambda e: self.run_file())
            self.root.bind("<%s-w>" % modifier, lambda e: self.close_current_tab())

    # -- Tab management -------------------------------------------------------

    def new_tab(self):
        """Open a fresh empty buffer in a new tab and switch to it."""
        tab = EditorTab(self.notebook, on_state_change=self._on_tab_state_change)
        self.tabs.append(tab)
        self.notebook.add(tab.frame, text=tab.title_label())
        self.notebook.select(tab.frame)
        tab.focus()
        return tab

    def _active_tab(self):
        """Return the currently selected tab (there is always at least one)."""
        return self.tabs[self.notebook.index("current")]

    def _on_tab_state_change(self, tab):
        """A tab's filename or modified flag changed: refresh its label/title."""
        try:
            self.notebook.tab(tab.frame, text=tab.title_label())
        except tk.TclError:
            return  # The tab isn't in the notebook yet (still being created).
        if tab is self._active_tab():
            self._update_title()

    def _on_tab_changed(self, event):
        """The user switched tabs: update the window title and focus the editor."""
        self._update_title()
        self._active_tab().focus()

    def _update_title(self):
        """Reflect the active tab's file and unsaved-changes state in the title."""
        self.root.title("%s - %s" % (self._active_tab().title_label(), config.WINDOW_TITLE))

    # -- Files ----------------------------------------------------------------

    def open_file(self):
        """Prompt for a file and open it in a tab (reusing an empty one if any)."""
        path = filedialog.askopenfilename(
            filetypes=[("Python files", "*.py"), ("All files", "*.*")]
        )
        if not path:
            return  # User cancelled the dialog.

        already_open = self._tab_for_path(path)
        if already_open is not None:
            self.notebook.select(already_open.frame)
            already_open.focus()
            return

        # Reuse the current tab if it's an untouched blank buffer; otherwise open
        # a new tab so we don't discard the user's work.
        target = self._active_tab()
        if not target.is_blank():
            target = self.new_tab()

        target.load(path)
        self.notebook.select(target.frame)
        target.focus()

    def _tab_for_path(self, path):
        """Return the tab already showing `path`, or None if none is."""
        wanted = os.path.abspath(path)
        for tab in self.tabs:
            if tab.filepath is not None and os.path.abspath(tab.filepath) == wanted:
                return tab
        return None

    def save_file(self):
        """Save the active tab (label/title refresh happens via its callback)."""
        self._active_tab().save()

    def save_file_as(self):
        self._active_tab().save_as()

    def close_current_tab(self):
        """Close the active tab, offering to save it first if it has changes."""
        tab = self._active_tab()
        if tab.has_unsaved_changes() and not self._offer_to_save(tab):
            return  # User cancelled the close.

        self.notebook.forget(tab.frame)
        self.tabs.remove(tab)
        tab.close()

        # The window always keeps at least one tab open.
        if not self.tabs:
            self.new_tab()

    def _offer_to_save(self, tab):
        """Ask whether to save `tab` before discarding it.

        Returns True if it is now safe to close the tab (saved, or the user chose
        to discard), or False if the user cancelled.
        """
        self.notebook.select(tab.frame)  # Show which tab we're asking about.
        answer = messagebox.askyesnocancel(
            "Unsaved changes",
            "Save changes to %s before closing?" % tab.display_name(),
        )
        if answer is None:
            return False   # Cancel.
        if answer:
            return tab.save()  # False if the save dialog was cancelled.
        return True            # Discard.

    def _on_close(self):
        """Handle the window's close button, offering to save every dirty tab."""
        for tab in list(self.tabs):
            if tab.has_unsaved_changes() and not self._offer_to_save(tab):
                return  # User cancelled: keep the window open.
        self.root.destroy()

    # -- Running --------------------------------------------------------------

    def run_file(self):
        """Execute the active tab's buffer and stream its output to the panel.

        Running never forces a save: we run exactly what's on screen. If the
        buffer is already saved and unchanged we run that file directly (so the
        working directory and relative imports behave naturally); otherwise we
        write the current text to a scratch file and run that. Either way we use
        this project's own Python interpreter -- the one running the editor.
        """
        tab = self._active_tab()
        run_path = self._path_to_run(tab)

        # Run from the file's own directory so relative paths work. When the file
        # has been saved, that directory is also its script directory, so its
        # sibling modules import normally. When we run a scratch copy instead, the
        # scratch lives in a temp directory, so we additionally put the real
        # directory on the import path so `from other_file import ...` still works.
        source_dir = os.path.dirname(tab.filepath) if tab.filepath else None
        running_scratch = run_path != tab.filepath
        import_dir = source_dir if running_scratch else None

        self._clear_output()
        self._append_output("$ python %s\n" % tab.display_name())
        self._run_queue = runner.start_run(
            sys.executable, run_path, cwd=source_dir, import_dir=import_dir
        )
        self._poll_run_output()

    def _path_to_run(self, tab):
        """Return a path holding the code to run: the real file or a scratch file."""
        if tab.filepath is not None and not tab.has_unsaved_changes():
            return tab.filepath

        if self._scratch_path is None:
            # mkstemp gives us a private file that survives the session; we own
            # it and simply overwrite it on each run.
            handle, self._scratch_path = tempfile.mkstemp(
                suffix=".py", prefix="local_auto_ide_"
            )
            os.close(handle)

        with open(self._scratch_path, "w") as scratch:
            scratch.write(tab.get_contents())
        return self._scratch_path

    def _poll_run_output(self):
        """Main-thread timer: drain run output until the program exits."""
        try:
            while True:
                kind, value = self._run_queue.get_nowait()
                if kind == "out":
                    self._append_output(value)
                elif kind == "done":
                    self._append_output("\n[process finished with exit code %s]\n" % value)
                    return  # Stop polling; the run is over.
        except queue.Empty:
            pass
        self.root.after(50, self._poll_run_output)

    def _append_output(self, text):
        """Append `text` to the read-only output panel and scroll to the end."""
        self.output.configure(state="normal")
        self.output.insert("end", text)
        self.output.see("end")
        self.output.configure(state="disabled")

    def _clear_output(self):
        """Empty the output panel before a new run."""
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")
