#!/usr/bin/env python3
"""fm-clone — A clone of Apple's Foundation Models CLI.

Commands:
    fm respond     Generate a response to a prompt
    fm chat        Start an interactive chat session
    fm token-count Count tokens in a prompt
    fm schema      Generate a JSON generation schema
    fm serve       Start a Chat Completions API server
    fm available   Check model availability
"""

import argparse
import json
import sys
from pathlib import Path

from src.api_client import chat_completion, count_tokens, check_availability
from src.render import render_markdown, render_text, render_error, stream_chunk, start_stream, end_stream
from src.config import get_default_model, set_default_model, load_config, save_config, get_api_config
from src.schema_builder import SchemaProperty, build_object, format_schema
from src.transcript import Transcript
from src.chat import run_chat
from src.serve import run_server

BANNER = r"""
   ____ ____ ____ ____ ____ ____ ____ ____ ____ ____
  ||f |||m |||- |||c |||l |||o |||n |||e |||  |||  ||
  ||__|||__|||__|||__|||__|||__|||__|||__|||__|||__||
  |/__\|/__\|/__\|/__\|/__\|/__\|/__\|/__\|/__\|/__\|
  Apple Foundation Models CLI — open-source reimplementation
"""


def show_banner():
    print(BANNER)


def main():
    parser = argparse.ArgumentParser(
        prog="fm",
        description="Apple Foundation Models CLI (open-source clone)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── respond ──
    resp = subparsers.add_parser("respond", help="Generate a response to a prompt")
    resp.add_argument("prompt", nargs="?", help="Prompt text")
    resp.add_argument("-m", "--model", default=None, help="Model to use")
    resp.add_argument("-i", "--instructions", help="Instructions for the model")
    resp.add_argument("--schema", type=str, help="Path to a JSON schema file or JSON string")
    resp.add_argument("--text", action="append", default=None, help="Additional text segments (repeatable)")
    resp.add_argument("--image", action="append", default=None, help="Image file paths (repeatable)")
    resp.add_argument("--load-transcript", type=str, help="Path to a saved transcript")
    resp.add_argument("--save-transcript", type=str, help="Save transcript after responding")
    resp.add_argument("--no-stream", dest="stream", action="store_false", default=True, help="Disable streaming output")
    resp.add_argument("-g", "--greedy", action="store_true", help="Use greedy sampling (temperature=0)")
    resp.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    # ── chat ──
    chat_p = subparsers.add_parser("chat", help="Start an interactive chat session")
    chat_p.add_argument("-m", "--model", default=None, help="Model to use")
    chat_p.add_argument("--set-default-model", help="Persist default model")
    chat_p.add_argument("-r", "--resume", help="Resume a saved chat session")
    chat_p.add_argument("--continue", dest="continue_session", action="store_true", help="Continue the most recent session")
    chat_p.add_argument("-i", "--instructions", help="Instructions for the model")

    # ── token-count ──
    tc = subparsers.add_parser("token-count", help="Count tokens in a prompt")
    tc.add_argument("prompt", nargs="?", help="Prompt text")
    tc.add_argument("-i", "--instructions", help="Instructions to include")
    tc.add_argument("--text", action="append", default=None, help="Additional text segments (repeatable)")
    tc.add_argument("--image", action="append", default=None, help="Image file paths (repeatable)")
    tc.add_argument("--load-transcript", help="Saved transcript to seed the count")
    tc.add_argument("-q", "--quiet", action="store_true", help="Print only the integer count")

    # ── schema ──
    sch = subparsers.add_parser("schema", help="Generate a JSON generation schema")
    sch_sub = sch.add_subparsers(dest="schema_command")
    obj = sch_sub.add_parser("object", help="Generate a JSON schema for an object type")
    obj.add_argument("--name", required=True, help="Name of the root object type")
    obj.add_argument("--string", action="append", default=None, help="Declare a string property")
    obj.add_argument("--int", action="append", default=None, dest="int_props", help="Declare an integer property")
    obj.add_argument("--integer", action="append", default=None, dest="int_props", help=argparse.SUPPRESS)
    obj.add_argument("--double", action="append", default=None, dest="double", help="Declare a floating-point property")
    obj.add_argument("--boolean", action="append", default=None, dest="boolean", help="Declare a boolean property")
    obj.add_argument("--object", action="append", default=None, dest="object_props", help="Declare a nested object property")
    obj.add_argument("--schema", action="append", default=None, dest="nested_schemas", help="JSON schema for preceding --object or --anyOf")
    obj.add_argument("--anyOf", action="store_true", default=False, help="Build an anyOf union")
    obj.add_argument("--array", action="store_true", default=False, help="Mark preceding property as array")
    obj.add_argument("--description", default=None, help="Set description on preceding property")
    obj.add_argument("--optional", action="store_true", default=False, help="Mark preceding property as optional")

    # ── serve ──
    srv = subparsers.add_parser("serve", help="Start a Chat Completions API server")
    srv.add_argument("--host", default="127.0.0.1", help="Host address")
    srv.add_argument("--port", type=int, default=1977, help="Port to listen on")
    srv.add_argument("--socket", dest="socket_path", help="Unix domain socket path")

    # ── available ──
    subparsers.add_parser("available", help="Check model availability")

    # ── quota-usage ──
    subparsers.add_parser("quota-usage", help="Check model quota usage")

    # ── config ──
    config_p = subparsers.add_parser("config", help="Manage configuration")
    config_p.add_argument("--set-api-key", help="Set API key")
    config_p.add_argument("--set-base-url", help="Set API base URL")
    config_p.add_argument("--set-model", help="Set default model name")
    config_p.add_argument("--show", action="store_true", help="Show current config")

    args = parser.parse_args()

    if not args.command:
        show_banner()
        parser.print_help()
        return

    if args.command == "config":
        handle_config(args)
        return

    if args.command == "respond":
        handle_respond(args)
    elif args.command == "chat":
        if args.set_default_model:
            set_default_model(args.set_default_model)
            render_text(f"Default model set to: {args.set_default_model}", "success")
            return
        if args.continue_session:
            latest = Transcript.latest_session()
            if latest:
                args.resume = str(latest)
                render_text(f"Continuing session: {latest.stem}", "info")
            else:
                render_error("No previous session found.")
                return
        show_banner()
        run_chat(instructions=args.instructions, resume=args.resume, model=args.model)
    elif args.command == "token-count":
        handle_token_count(args)
    elif args.command == "schema":
        handle_schema(args)
    elif args.command == "serve":
        handle_serve(args)
    elif args.command == "available":
        handle_available(args)
    elif args.command == "quota-usage":
        handle_quota_usage(args)


def handle_respond(args):
    prompt = args.prompt or sys.stdin.read().strip()
    if not prompt:
        render_error("Error: No prompt provided.")
        return

    instructions = args.instructions

    if args.load_transcript:
        transcript = Transcript.load(args.load_transcript)
    else:
        transcript = Transcript(instructions=instructions)

    transcript.add_user_prompt(prompt)
    messages = transcript.get_messages_for_api()

    schema = None
    if args.schema:
        try:
            schema = json.loads(args.schema)
        except json.JSONDecodeError:
            try:
                schema = json.loads(Path(args.schema).read_text())
            except Exception:
                render_error(f"Invalid schema: {args.schema}")
                return
        if "json_schema" in schema:
            schema = schema["json_schema"]
        elif "type" not in schema:
            schema = None

    temperature = 0.0 if args.greedy else 0.7

    if args.stream:
        start_stream()
        full = ""
        try:
            for chunk in chat_completion(messages, stream=True, schema=schema, temperature=temperature, model=args.model):
                full += chunk
                stream_chunk(full)
            end_stream()
            render_text("")
        except Exception as e:
            end_stream()
            render_error(f"Error: {e}")
            return
    else:
        try:
            result = chat_completion(messages, stream=False, schema=schema, temperature=temperature, model=args.model)
            render_markdown(result)
        except Exception as e:
            render_error(f"Error: {e}")
            return
        full = result

    if args.save_transcript:
        transcript.add_response(full)
        transcript.save(args.save_transcript)
        render_text(f"Transcript saved: {args.save_transcript}", "dim")


def handle_token_count(args):
    text = args.prompt or sys.stdin.read().strip()
    if args.instructions:
        text = f"{args.instructions}\n\n{text}"
    if args.text:
        text = "\n".join(args.text) + "\n" + text
    if args.load_transcript:
        try:
            transcript = Transcript.load(args.load_transcript)
            messages = transcript.get_messages_for_api()
            text = json.dumps(messages)
        except Exception as e:
            render_error(f"Failed to load transcript: {e}")
            return
    count = count_tokens(text)
    if args.quiet or not sys.stdout.isatty():
        print(count)
    else:
        render_text(f"Token count: {count}", "info")


def handle_schema(args):
    if args.schema_command != "object":
        render_error("Use: fm schema object --name <name> [--string <prop> ...]")
        return

    properties = []
    for name in (args.string or []):
        properties.append(SchemaProperty(name, "string"))
    for name in (args.int_props or []):
        properties.append(SchemaProperty(name, "integer"))
    for name in (args.double or []):
        properties.append(SchemaProperty(name, "number"))
    for name in (args.boolean or []):
        properties.append(SchemaProperty(name, "boolean"))

    nested_schemas = args.nested_schemas or []
    for i, name in enumerate(args.object_props or []):
        nested = None
        if i < len(nested_schemas):
            try:
                nested = json.loads(nested_schemas[i])
                if "json_schema" in nested:
                    nested = nested["json_schema"]
            except json.JSONDecodeError:
                pass
        properties.append(SchemaProperty(name, "object", nested_schema=nested))

    if properties and args.array:
        properties[-1].is_array = True
    if properties and args.description:
        properties[-1].description = args.description
    if properties and args.optional:
        properties[-1].is_optional = True

    any_of_schemas = None
    if args.anyOf:
        any_of_schemas = []
        for s in nested_schemas:
            try:
                parsed = json.loads(s)
                if "json_schema" in parsed:
                    parsed = parsed["json_schema"]
                any_of_schemas.append(parsed)
            except json.JSONDecodeError:
                pass

    schema = build_object(args.name, properties, any_of_schemas)
    print(format_schema(schema))


def handle_serve(args):
    render_text(f"Starting fm-clone API server on {args.host}:{args.port}", "info")
    render_text("Endpoints:", "dim")
    render_text("  POST /v1/chat/completions", "dim")
    render_text("  GET  /v1/models", "dim")
    render_text("  GET  /health", "dim")
    render_text("")
    run_server(host=args.host, port=args.port, socket_path=args.socket_path)


def handle_available(args):
    result = check_availability()
    if result["available"]:
        render_text(f"  Model available: {result['model']}", "success")
        render_text(f"  Provider: {result['provider']}", "dim")
    else:
        render_error(f"  Model unavailable: {result.get('error', 'Unknown error')}")
        render_text("  Configure with: fm config --set-api-key <key>", "dim")


def handle_quota_usage(args):
    cfg = get_api_config()
    render_text(f"  Provider: {cfg['base_url']}", "info")
    render_text(f"  Model: {cfg['model']}", "info")
    render_text(f"  Quota tracking depends on your API provider.", "dim")


def handle_config(args):
    if args.set_api_key:
        cfg = load_config()
        cfg["api_key"] = args.set_api_key
        save_config(cfg)
        render_text("API key saved.", "success")
    elif args.set_base_url:
        cfg = load_config()
        cfg["base_url"] = args.set_base_url
        save_config(cfg)
        render_text(f"Base URL set to: {args.set_base_url}", "success")
    elif args.set_model:
        cfg = load_config()
        cfg["model"] = args.set_model
        save_config(cfg)
        render_text(f"Default model set to: {args.set_model}", "success")
    elif args.show:
        cfg = load_config()
        render_text("Current configuration:", "heading")
        for k, v in cfg.items():
            if k == "api_key":
                v = (v[:8] + "..." if len(v) > 8 else v) if v else "(not set)"
            render_text(f"  {k}: {v}")
    else:
        cfg = load_config()
        render_text("Current configuration:", "heading")
        api_key = cfg.get("api_key", "")
        base_url = cfg.get("base_url", "https://api.openai.com/v1")
        model = cfg.get("model", "gpt-4o-mini")
        render_text(f"  base_url: {base_url}")
        render_text(f"  model: {model}")
        render_text(f"  api_key: {'****' + api_key[-4:] if len(api_key) > 4 else '(not set)'}")


if __name__ == "__main__":
    main()
