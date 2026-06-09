"""Terminal rendering — colors, logo, markdown, streaming TUI."""

import sys
import shutil
import time
from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.style import Style

# ── color palette from original fm ──────────────────────────────────
GREEN  = (130, 215, 90)
CYAN   = (55, 195, 160)
GRAY   = (153, 153, 153)
RED    = (255, 107, 128)
YELLOW = (255, 193, 7)
BLUE   = (35, 130, 205)

_console: Console = None
_current_theme: str = "auto"


def _get_width():
    try: return shutil.get_terminal_size().columns
    except Exception: return 80


def _get_height():
    try: return shutil.get_terminal_size().lines
    except Exception: return 24


def _rgb(r, g, b): return f"rgb({r},{g},{b})"


# ── gradient helpers ────────────────────────────────────────────────
def _lerp(a, b, t): return int(a + (b - a) * t)


def _gradient(t: float) -> tuple[int, int, int]:
    """Green → Cyan → Blue gradient, matching original fm."""
    if t < 0.5:
        s = t / 0.5
        return (_lerp(GREEN[0], CYAN[0], s),
                _lerp(GREEN[1], CYAN[1], s),
                _lerp(GREEN[2], CYAN[2], s))
    else:
        s = (t - 0.5) / 0.5
        return (_lerp(CYAN[0], BLUE[0], s),
                _lerp(CYAN[1], BLUE[1], s),
                _lerp(CYAN[2], BLUE[2], s))


# ── exact logo data extracted from original fm binary ────────────────
LOGO_ROWS = [
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⠞⠛⠳⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣀⣿⡀⠀⢀⣽⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⣀⣤⠴⠚⠋⢁⡼⠛⠛⠛⢧⡈⠙⠓⠦⣤⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⢠⡶⠒⠲⣦⣠⡴⠞⠋⠉⠀⠀⠀⣴⠟⠀⠀⠀⠀⠀⠹⣆⠀⠀⠀⠈⠙⠲⠦⣄⣠⠖⠒⢦⡀",
    "⢿⡀⠀⠀⣸⣇⠀⠀⠀⠀⠀⣠⡾⠁⠀⠀⠀⠀⠀⠀⠀⠈⢳⡄⠀⠀⠀⠀⠀⣨⣇⠀⠀⢀⡿",
    "⠈⠛⠲⠚⢿⡍⠙⠳⢦⣤⣴⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⣦⣠⠴⠖⠋⢁⡽⠓⠒⠋⠁",
    "⠀⠀⠀⠀⠀⠹⣦⡀⣠⠟⠉⠛⠲⢦⣄⣠⡴⠶⢦⣄⣠⡤⠖⠛⠉⠳⣄⠀⣴⠋⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⢈⣿⣏⠀⠀⠀⠀⠀⢈⣿⠀⠀⠀⣿⡁⠀⠀⠀⠀⠀⣸⣿⡁⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⣴⠟⠀⠙⣧⣀⣤⠶⠚⠋⠙⠳⠶⠞⠋⠙⠓⠦⣤⣀⡴⠋⠀⠹⣄⠀⠀⠀⠀⠀",
    "⢀⣤⠶⢦⣾⣃⣤⡴⠞⠋⠻⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⠟⠙⠒⠦⣄⡈⣳⡤⠤⢤⡀",
    "⣿⠁⠀⠀⢹⡏⠀⠀⠀⠀⠀⠙⢷⡀⠀⠀⠀⠀⠀⠀⠀⢀⡾⠃⠀⠀⠀⠀⠀⢉⡏⠀⠀⠀⡷",
    "⠘⠷⠦⠶⠟⠙⠳⢦⣤⣀⠀⠀⠀⠻⣦⠀⠀⠀⠀⠀⣴⠏⠀⠀⠀⣀⣠⠴⠒⠋⠙⠦⠤⠞⠁",
]
LOGO_WIDTH = 39

# animation frames: offset the gradient for a scrolling rainbow effect
ANIM_FRAMES = 8


def _console_for_theme(theme: str = "auto") -> Console:
    if theme == "dark":
        return Console(color_system="truecolor")
    elif theme == "light":
        return Console(color_system="truecolor")
    else:
        return Console(color_system="truecolor")


# ── logo rendering ──────────────────────────────────────────────────
def render_logo(anim_frame: int = 0):
    """Render the gradient Braille-art 'fm' logo."""
    console = _get_console()
    rows = len(LOGO_ROWS)
    for r in range(rows):
        line = Text()
        row_chars = LOGO_ROWS[r]
        for c, ch in enumerate(row_chars):
            t = (c + anim_frame * 3) / (LOGO_WIDTH + ANIM_FRAMES * 3)
            r_val, g_val, b_val = _gradient(t % 1.0)
            line.append(ch, style=Style(color=_rgb(r_val, g_val, b_val)))
        console.print(line)


def animate_logo(duration: float = 1.2):
    """Brief animated rainbow scroll on the logo, like original fm."""
    frames = ANIM_FRAMES
    import sys
    for f in range(frames):
        console = _get_console()
        if f > 0:
            sys.stdout.write(f"\033[{len(LOGO_ROWS)}A")  # cursor up
        render_logo(anim_frame=f)
        sys.stdout.flush()
        time.sleep(duration / frames)


def show_logo():
    """Show the static logo (no animation)."""
    render_logo(anim_frame=0)


# ── singleton console ───────────────────────────────────────────────
def _get_console() -> Console:
    global _console
    if _console is None:
        _console = Console(width=_get_width(), color_system="truecolor")
    return _console


# ── rendering functions ─────────────────────────────────────────────
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
    elif style == "cyan":
        console.print(Text(text, style=_rgb(*CYAN)))
    else:
        console.print(text)


def render_prompt(prompt: str):
    if sys.stdout.isatty():
        render_text(f"> {prompt}", "dim")
    else:
        print(f"> {prompt}")


def render_error(msg: str):
    render_text(f"  {msg}", "error")


def start_stream():
    global _live, _buffer
    _buffer = ""
    console = _get_console()
    _live = Live(Text(""), console=console, refresh_per_second=20, vertical_overflow="visible")
    _live.start()


def stream_chunk(full_text: str):
    global _live
    if _live:
        try:
            _live.update(Markdown(full_text, code_theme="monokai"))
        except Exception:
            _live.update(Text(full_text))


_buffer = ""
_live: Live = None


def end_stream():
    global _live, _buffer
    if _live:
        _live.stop()
        _live = None
    result = _buffer
    _buffer = ""
    return result


# ── appearance ──────────────────────────────────────────────────────
def set_theme(mode: str):
    global _current_theme
    _current_theme = mode


def get_theme() -> str:
    return _current_theme
