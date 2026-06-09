import re
import sys
import shutil
from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text
from rich.live import Live
from rich.style import Style

_console: Console = None
_live: Live = None
_buffer: str = ""
_width: int = None


def _get_console() -> Console:
    global _console
    if _console is None:
        try:
            w = shutil.get_terminal_size().columns
        except Exception:
            w = 80
        _console = Console(width=w)
    return _console


def _get_width():
    global _width
    if _width is None:
        try:
            _width = shutil.get_terminal_size().columns
        except Exception:
            _width = 80
    return _width


def render_markdown(text: str):
    console = _get_console()
    md = Markdown(text)
    console.print(md)


def render_text(text: str, style: str = ""):
    console = _get_console()
    if style == "bold":
        console.print(Text(text, style="bold"))
    elif style == "heading":
        console.print(Text(text, style="bold underline"))
    elif style == "dim":
        console.print(Text(text, style="dim"))
    elif style == "error":
        console.print(Text(text, style="bold red"))
    elif style == "success":
        console.print(Text(text, style="bold green"))
    elif style == "info":
        console.print(Text(text, style="cyan"))
    else:
        console.print(text)


def start_stream():
    global _buffer, _live
    _buffer = ""
    console = _get_console()
    _live = Live(Text(""), console=console, refresh_per_second=20, vertical_overflow="visible")
    _live.start()


def stream_chunk(chunk: str):
    global _buffer
    _buffer += chunk
    if _live:
        try:
            md = Markdown(_buffer, code_theme="monokai")
            _live.update(md)
        except Exception:
            _live.update(Text(_buffer))


def end_stream():
    global _buffer, _live
    if _live:
        _live.stop()
        _live = None
    result = _buffer
    _buffer = ""
    return result


def render_prompt(prompt: str):
    render_text(f"\n> {prompt}\n", "dim")


def render_user_input(text: str):
    render_text(f"\nYou: {text}", "bold")


def render_error(msg: str):
    render_text(f"  {msg}", "error")


def render_help(commands: list[tuple[str, str]]):
    width = _get_width()
    for cmd, desc in commands:
        padded = cmd.ljust(20)
        render_text(f"  {padded}{desc}")
