"""Interactive chat TUI — replicates original fm chat TopPane/BottomPane layout."""

import os
import readline
import sys
from .transcript import Transcript
from .api_client import chat_completion
from .render import (
    render_markdown, render_text, render_error,
    start_stream, stream_chunk, end_stream,
    show_logo, animate_logo, set_theme, get_theme,
)
from .config import get_default_model

# Track current model in chat session
_current_model: str = None


def _ensure_readline_history():
    histfile = os.path.expanduser("~/.fm-clone/.history")
    try:
        readline.read_history_file(histfile)
    except FileNotFoundError:
        pass
    import atexit
    atexit.register(lambda: readline.write_history_file(histfile))


def run_chat(
    instructions: str = None,
    resume: str = None,
    model: str = None,
    continue_session: bool = False,
):
    global _current_model
    _current_model = model or get_default_model()

    if continue_session:
        latest = Transcript.latest_session()
        if latest:
            resume = str(latest)
            render_text(f"Continuing session: {latest.stem}", "info")
        else:
            render_error("No previous session found.")
            return

    if resume:
        transcript = Transcript.load(resume)
        if instructions:
            transcript.set_instructions(instructions)
        render_text(f"Resumed session: {resume}", "info")
    else:
        transcript = Transcript(model_name=_current_model, instructions=instructions)

    instr = transcript.get_instructions()
    if instr:
        render_text(f"Instructions: {instr[:100]}{'...' if len(instr) > 100 else ''}", "info")

    _ensure_readline_history()

    # ── animated logo then chat header ─────────────────────────────
    if sys.stdout.isatty():
        animate_logo(duration=0.8)
    render_text(f"\n  Apple Foundation Models Chat", "heading")

    while True:
        try:
            prompt = input("fm> ").strip()
        except (EOFError, KeyboardInterrupt):
            render_text("\n  Goodbye!", "dim")
            break

        if not prompt:
            continue

        if prompt.startswith("/"):
            result = _handle_command(prompt, transcript)
            if result == "quit":
                break
            continue

        # ── user message ──────────────────────────────────────────
        transcript.add_user_prompt(prompt)
        render_user_bubble(prompt)

        # ── model response ─────────────────────────────────────────
        messages = transcript.get_messages_for_api()
        try:
            start_stream()
            full_response = ""
            for chunk in chat_completion(messages, stream=True, model=_current_model):
                full_response += chunk
                stream_chunk(full_response)
            end_stream()
            transcript.add_response(full_response)
            print()
        except Exception as e:
            end_stream()
            render_error(f"Error: {e}")

        # ── auto-save ──────────────────────────────────────────────
        try:
            transcript.save("latest")
        except Exception:
            pass


def render_user_bubble(text: str):
    render_text(f"\n  {text}", "dim")


def _handle_command(cmd: str, transcript: Transcript) -> str | None:
    global _current_model
    parts = cmd.split(maxsplit=1)
    action = parts[0].lower().strip()
    arg = parts[1] if len(parts) > 1 else ""

    if action in ("/quit", "/exit", "/q"):
        return "quit"

    elif action == "/help":
        _show_help()

    elif action == "/instructions":
        if arg:
            transcript.set_instructions(arg)
            render_text(f"  Instructions updated.", "success")
        else:
            instr = transcript.get_instructions()
            if instr:
                render_text(f"  Instructions: {instr}", "info")
            else:
                render_text("  No instructions set.", "dim")

    elif action == "/model":
        if arg:
            valid_models = ["system", "pcc"]
            if arg in valid_models:
                _current_model = arg
                transcript.model_name = arg
                render_text(f"  Switched to model: {arg}", "success")
            else:
                render_error(f"  Unknown model: {arg}. Valid: system, pcc")
        else:
            render_text(f"  Current model: {_current_model}", "info")

    elif action == "/save":
        name = arg or None
        path = transcript.save(name)
        render_text(f"  Session saved: {path.name}", "success")

    elif action == "/load":
        if arg:
            try:
                new_t = Transcript.load(arg)
                transcript.entries = new_t.entries
                _current_model = new_t.model_name
                transcript.model_name = new_t.model_name
                render_text(f"  Loaded session: {arg}", "success")
            except Exception as e:
                render_error(f"  Failed to load: {e}")
        else:
            render_error("  Usage: /load <name>")

    elif action == "/history":
        sessions = Transcript.list_sessions()
        if sessions:
            render_text("  Saved sessions:", "heading")
            for s in sessions[:20]:
                render_text(f"    {s.stem}")
        else:
            render_text("  No saved sessions.", "dim")

    elif action == "/clear":
        transcript.entries = [e for e in transcript.entries if e["role"] == "instructions"]
        render_text("  Session cleared.", "success")

    elif action == "/appearance":
        valid = ["dark", "light", "auto"]
        if arg in valid:
            set_theme(arg)
            render_text(f"  Appearance set to: {arg}", "success")
        else:
            render_text(f"  Current appearance: {get_theme()}", "info")
            render_text(f"  Usage: /appearance dark|light|auto", "dim")

    elif action == "/increase-limit":
        render_error("  /increase-limit is only available for the PCC model.")

    else:
        render_error(f"  Unknown command: {action}. Type /help for available commands.")

    return None


def _show_help():
    commands = [
        ("/help", "Show this help"),
        ("/instructions [text]", "Set or view system instructions"),
        ("/model <system|pcc>", "Switch model"),
        ("/save [name]", "Save current session"),
        ("/load <name>", "Load a saved session"),
        ("/history", "List saved sessions"),
        ("/clear", "Start a new session"),
        ("/appearance <mode>", "Set appearance: dark, light, auto"),
        ("/increase-limit", "Increase PCC context limit"),
        ("/quit, /exit", "Exit chat"),
    ]
    render_text("  Available commands:", "heading")
    for cmd, desc in commands:
        render_text(f"    {cmd.ljust(24)} {desc}")
    render_text("")
