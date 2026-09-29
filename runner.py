"""Run a Python file and stream its output back to the caller.

The Run button needs to execute the user's file without freezing the editor,
and show the output as it is produced. We launch the interpreter as a
subprocess on a background thread and forward each line of its combined
stdout/stderr into a thread-safe queue. The UI drains that queue on the main
thread (see the editor's run-polling code), which keeps all Tkinter access on
the one thread where it is safe.
"""

import os
import queue
import subprocess
import threading


def start_run(interpreter, path, cwd=None, import_dir=None):
    """Start running `path` with `interpreter`; return a queue of output events.

    `cwd` sets the program's working directory, so relative file paths in the
    code resolve the way the user expects. `import_dir`, when given, is added to
    the module search path (PYTHONPATH) so the program can import its sibling
    modules -- this matters when we run a temporary copy of a file, which
    otherwise wouldn't see the other files in the user's project.

    The returned queue yields tuples:
      ("out", text)      -- a chunk of program output (stdout or stderr)
      ("done", code)     -- the program has exited with this return code

    The caller polls the queue on the main thread and stops once it sees
    "done". Running happens on a daemon thread so it never blocks the UI or
    keeps the app alive after the window closes.
    """
    output = queue.Queue()

    def work():
        try:
            process = subprocess.Popen(
                [interpreter, path],
                cwd=cwd,
                env=_environment_with_import_dir(import_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge errors into the same stream.
                text=True,
                bufsize=1,  # Line-buffered, so output appears as it is printed.
            )
        except OSError as error:
            output.put(("out", "Could not start the program: %s\n" % error))
            output.put(("done", -1))
            return

        # Forward output line by line until the program closes its stdout.
        for line in process.stdout:
            output.put(("out", line))
        process.wait()
        output.put(("done", process.returncode))

    threading.Thread(target=work, daemon=True).start()
    return output


def _environment_with_import_dir(import_dir):
    """Return an environment dict with `import_dir` prepended to PYTHONPATH.

    Returns None (meaning "inherit our own environment unchanged") when there is
    no directory to add, so the common case stays simple.
    """
    if not import_dir:
        return None
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    # Prepend so the user's own modules take priority, joining with the
    # platform's path separator (":" on macOS/Linux, ";" on Windows).
    env["PYTHONPATH"] = import_dir + (os.pathsep + existing if existing else "")
    return env
