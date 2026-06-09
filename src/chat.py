import os
import readline
import sys
from .transcript import Transcript
from .api_client import chat_completion, count_tokens
from .render import (
    render_markdown, render_text, render_prompt, render_user_input,
    render_error, render_help, start_stream, stream_chunk, end_stream
)
from .config import get_default_model


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
):
    model = model or get_default_model()

    if resume:
        transcript = Transcript.load(resume)
        if instructions:
            transcript.set_instructions(instructions)
        render_text(f"Resumed session: {resume}", "info")
    else:
        transcript = Transcript(model_name=model, instructions=instructions)

    if instructions:
        render_text(f"Instructions: {instructions[:80]}{'...' if len(instructions) > 80 else ''}", "info")

    _ensure_readline_history()
    render_text(f"\n  Apple Foundation Models Chat (fm-clone)\n", "heading")

    while True:
        try:
            user_input = input("fm> ").strip()
        except (EOFError, KeyboardInterrupt):
            render_text("\n  Goodbye!", "dim")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            _handle_command(user_input, transcript, model)
            continue

        transcript.add_user_prompt(user_input)
        render_user_input(user_input)

        messages = transcript.get_messages_for_api()

        try:
            render_prompt("Generating...")
            start_stream()
            full_response = ""
            for chunk in chat_completion(messages, stream=True, model=model):
                full_response += chunk
                stream_chunk(full_response)
            end_stream()
            transcript.add_response(full_response)
            render_text("")
        except Exception as e:
            end_stream()
            render_error(f"Error: {e}")


def _handle_command(cmd: str, transcript: Transcript, model: str):
    parts = cmd.split(maxsplit=1)
    action = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if action == "/help":
        commands = [
            ("/help", "Show this help"),
            ("/instructions [text]", "Set or view system instructions"),
            ("/model <name>", "Switch model"),
            ("/save [name]", "Save current session"),
            ("/load <name>", "Load a saved session"),
            ("/history", "List saved sessions"),
            ("/clear", "Start a new session"),
            ("/quit, /exit", "Exit chat"),
        ]
        render_text("\nAvailable commands:", "heading")
        render_help(commands)
        render_text("")

    elif action == "/instructions":
        if arg:
            transcript.set_instructions(arg)
            render_text(f"Instructions updated.", "success")
        else:
            instr = transcript.get_instructions()
            if instr:
                render_text(f"Instructions: {instr}", "info")
            else:
                render_text("No instructions set.", "dim")

    elif action == "/model":
        if arg:
            model = arg
            render_text(f"Switched to model: {model}", "success")
        else:
            render_text(f"Current model: {model}", "info")

    elif action == "/save":
        name = arg or None
        path = transcript.save(name)
        render_text(f"Session saved: {path.name}", "success")

    elif action == "/load":
        if arg:
            try:
                new_t = Transcript.load(arg)
                transcript.entries = new_t.entries
                transcript.model_name = new_t.model_name
                render_text(f"Loaded session: {arg}", "success")
            except Exception as e:
                render_error(f"Failed to load: {e}")
        else:
            render_error("Usage: /load <name>")

    elif action == "/history":
        sessions = Transcript.list_sessions()
        if sessions:
            render_text("\nSaved sessions:", "heading")
            for s in sessions[:20]:
                render_text(f"  {s.stem}")
            render_text("")
        else:
            render_text("No saved sessions.", "dim")

    elif action == "/clear":
        transcript.entries = [e for e in transcript.entries if e["role"] == "instructions"]
        render_text("Session cleared.", "success")

    elif action in ("/quit", "/exit", "/q"):
        raise EOFError

    else:
        render_error(f"Unknown command: {action}. Type /help for available commands.")
