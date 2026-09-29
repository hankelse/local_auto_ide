"""A Text widget that announces whenever its content or view changes.

Tkinter's Text widget fires events for keystrokes, but *not* for every way its
contents or scroll position can change: pasting, programmatic edits, and mouse
-wheel scrolling can all move things without a key ever being pressed. The line
-number gutter needs to redraw on all of those, so we need a more reliable
signal than key bindings.

The robust, standard technique (popularised by Bryan Oakley) is to intercept
the widget at the Tcl level. Every Tk widget is backed by a Tcl command; we
rename that command aside and install our own wrapper in its place. The wrapper
calls the real command, then emits one of two custom events so listeners can
react precisely:

  * ``<<TextModified>>`` -- the text content changed (insert/delete/replace);
  * ``<<TextScrolled>>`` -- only the visible region moved (scrolling).

The gutter listens for both (it must redraw either way); the syntax highlighter
listens only for ``<<TextModified>>``, so it does not re-tokenise on every
scroll tick.

This is the one genuinely non-obvious mechanism in the project, which is why it
lives in its own small module with this explanation. Everything else uses the
widget exactly like a normal ``tk.Text``.
"""

import tkinter as tk


# Tcl subcommands that can change the text content or the visible region, and
# therefore should trigger a gutter redraw.
_CHANGE_COMMANDS = {"insert", "delete", "replace"}
_VIEW_COMMANDS = {"yview", "xview", "see"}


class CodeText(tk.Text):
    """A ``tk.Text`` that emits ``<<TextModified>>`` on content/view changes."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._install_command_proxy()

    def _install_command_proxy(self):
        """Replace the widget's Tcl command with a wrapper we control.

        After this runs, every call the Tk machinery makes to this widget
        (``self.insert(...)``, scrolling, etc.) passes through ``_proxy`` first.
        """
        # The real widget command is renamed from e.g. ".text" to ".text_orig".
        self._original_command = str(self) + "_orig"
        self.tk.call("rename", str(self), self._original_command)
        # Our Python method takes its place under the widget's own name.
        self.tk.createcommand(str(self), self._proxy)

    def _proxy(self, *args):
        """Run the real command, then emit an event if something changed."""
        try:
            result = self.tk.call((self._original_command,) + args)
        except tk.TclError:
            # The real Text command raises for harmless things like deleting
            # past the start of the document. We swallow these exactly as the
            # normal widget would, so behaviour is unchanged.
            return ""

        # `when="tail"` queues the event so it fires after this command fully
        # finishes, avoiding re-entrancy while we are mid-edit.
        subcommand = args[0] if args else ""
        if subcommand in _CHANGE_COMMANDS:
            self.event_generate("<<TextModified>>", when="tail")
        elif subcommand in _VIEW_COMMANDS:
            self.event_generate("<<TextScrolled>>", when="tail")

        return result
