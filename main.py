"""Entry point: open the editor window.

Run it through the project's virtual environment, which has a modern Tkinter:

    ./venv/bin/python main.py

or use the convenience script `./run.sh`.

Ollama must be running locally (`ollama serve`) with the model named in
config.py already pulled (`ollama pull llama3.2:3b`). If Ollama is unreachable
the editor still works as a plain text editor; suggestions simply won't appear.
"""

import tkinter as tk

from editor import Editor


def main():
    root = tk.Tk()
    Editor(root)
    root.mainloop()


if __name__ == "__main__":
    main()
