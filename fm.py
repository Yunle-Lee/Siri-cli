#!/usr/bin/env python3
"""fm — Apple Foundation Models CLI (open-source clone).

Commands:
    fm respond      Generate a response to a prompt
    fm chat         Start an interactive chat session
    fm token-count  Count tokens in a prompt or instructions
    fm schema       Generate a JSON generation schema
    fm serve        Start a Chat Completions API server
    fm available    Check model availability
    fm quota-usage  Check model quota usage
"""

import argparse
import json
import sys
from pathlib import Path

from src.api_client import chat_completion, count_tokens, check_availability, image_token_count
from src.render import (
    render_markdown, render_text, render_error, render_prompt,
    start_stream, stream_chunk, end_stream, show_logo, animate_logo,
    CYAN, GRAY,
)
from src.config import get_default_model, set_default_model, load_config, save_config, get_api_config
from src.schema_builder import SchemaProperty, build_object, format_schema
from src.transcript import Transcript
from src.chat import run_chat
from src.serve import run_server


def _rgb(r, g, b): return f"\033[38;2;{r};{g};{b}m"
BOLD = "\033[1m"
RESET = "\033[0m"
DIM = "\033[2m"
ITALIC = "\033[3m"
GREEN_HEX = _rgb(*CYAN)
GRAY_HEX = _rgb(*GRAY)


def main():
    parser = argparse.ArgumentParser(
        prog="fm",
        description="Apple Foundation Models CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="store_true", help="Show help information")

    subparsers = parser.add_subparsers(dest="command")

    # ── respond ────────────────────────────────────────────────────
    resp = subparsers.add_parser("respond", add_help=False,
        help="Generate a response to a prompt",
        description="Generate a response to a prompt.")
    resp.add_argument("prompt", nargs="?", help="Prompt for the model to respond to")
    resp.add_argument("-m", "--model", default=None,
        help="Model to use (system, pcc)")
    resp.add_argument("-i", "--instructions", help="Instructions for the model to follow")
    resp.add_argument("--schema", type=str, help="Path to a JSON schema file")
    resp.add_argument("--text", action="append", default=None, help="Text segment to include in the prompt")
    resp.add_argument("--image", action="append", default=None, help="Image file path to include in the prompt")
    resp.add_argument("--load-transcript", type=str, help="Path to a saved transcript")
    resp.add_argument("--save-transcript", type=str, help="Save transcript after responding")
    resp.add_argument("--no-stream", dest="stream", action="store_false", default=True,
        help="Stream the output as it's generated (default: on)")
    resp.add_argument("-g", "--greedy", action="store_true", help="Use greedy sampling")
    resp.add_argument("-v", "--verbose", action="store_true", help="Print verbose output")
    resp.add_argument("--use-case", default="general",
        help="Model use case (general, content-tagging)")
    resp.add_argument("--guardrails", default="default",
        help="Guardrail level (default, permissive-content-transformations)")
    resp.add_argument("-h", "--help", action="store_true", help="Show help information")

    # ── chat ───────────────────────────────────────────────────────
    chat_p = subparsers.add_parser("chat", add_help=False,
        help="Start an interactive chat session",
        description="Start an interactive chat session.")
    chat_p.add_argument("-m", "--model", default=None, help="Model to use (system, pcc)")
    chat_p.add_argument("--set-default-model", help="Persist default model (system or pcc)")
    chat_p.add_argument("-r", "--resume", help="Resume a saved chat session")
    chat_p.add_argument("--continue", dest="continue_session", action="store_true",
        help="Continue the most recent chat session")
    chat_p.add_argument("-i", "--instructions", help="Instructions for the model")
    chat_p.add_argument("-h", "--help", action="store_true", help="Show help information")

    # ── token-count ────────────────────────────────────────────────
    tc = subparsers.add_parser("token-count", add_help=False,
        help="Count tokens in a prompt or instructions",
        description="Count the tokens in a prompt, instructions, or saved transcript.")
    tc.add_argument("prompt", nargs="?", help="Prompt to count tokens for")
    tc.add_argument("-i", "--instructions", help="Instructions to include in the count")
    tc.add_argument("--text", action="append", default=None, help="Additional text segment to include (repeatable)")
    tc.add_argument("--image", action="append", default=None, help="Image to include in the prompt (repeatable)")
    tc.add_argument("--load-transcript", help="Saved transcript to seed the count")
    tc.add_argument("-q", "--quiet", action="store_true", help="Print only the integer count")
    tc.add_argument("-h", "--help", action="store_true", help="Show help information")

    # ── schema ─────────────────────────────────────────────────────
    sch = subparsers.add_parser("schema", add_help=False,
        help="Generate a JSON generation schema",
        description="Generate a JSON generation schema.")
    sch.add_argument("-h", "--help", action="store_true", help="Show help information")
    sch_sub = sch.add_subparsers(dest="schema_command")
    obj = sch_sub.add_parser("object", add_help=False,
        help="Generate a JSON schema for an object type",
        description="Generate a JSON schema for an object type.")
    obj.add_argument("--name", required=True, help="Name of the root object type (required)")
    obj.add_argument("--string", action="append", default=None, help="Declare a string property")
    obj.add_argument("--integer", "--int", action="append", default=None, dest="integer", help="Declare an integer property")
    obj.add_argument("--double", action="append", default=None, help="Declare a floating-point property")
    obj.add_argument("--boolean", action="append", default=None, help="Declare a boolean property")
    obj.add_argument("--object", action="append", default=None, dest="object_props", help="Declare a nested object property (follow with --schema)")
    obj.add_argument("--schema", action="append", default=None, dest="nested_schemas",
        help="Provide a JSON schema (after --object or --anyOf)")
    obj.add_argument("--anyOf", action="store_true", default=False,
        help="Build an anyOf union; subsequent --schema args become choices")
    obj.add_argument("--array", action="store_true", default=False,
        help="Mark the preceding property as an array of that type")
    obj.add_argument("--description", default=None, help="Set a description on the preceding property")
    obj.add_argument("--optional", action="store_true", default=False,
        help="Mark the preceding property as optional")
    obj.add_argument("-h", "--help", action="store_true", help="Show help information")

    # ── serve ──────────────────────────────────────────────────────
    srv = subparsers.add_parser("serve", add_help=False,
        help="Start a Chat Completions API server",
        description="Start a Chat Completions API server for Foundation Models.")
    srv.add_argument("--host", default="127.0.0.1", help="Host address to bind to (TCP mode)")
    srv.add_argument("--port", type=int, default=1977, help="Port to listen on, 1-65535 (TCP mode)")
    srv.add_argument("--socket", dest="socket_path", help="Unix domain socket path (socket mode)")
    srv.add_argument("-h", "--help", action="store_true", help="Show help information")

    # ── available ──────────────────────────────────────────────────
    subparsers.add_parser("available", add_help=False,
        help="Check model availability")

    # ── quota-usage ────────────────────────────────────────────────
    subparsers.add_parser("quota-usage", add_help=False,
        help="Check model quota usage")

    # ── config (extra, not in original) ────────────────────────────
    config_p = subparsers.add_parser("config", add_help=False,
        help="Manage API configuration")
    config_p.add_argument("--set-api-key", help="Set API key")
    config_p.add_argument("--set-base-url", help="Set API base URL")
    config_p.add_argument("--set-model", help="Set default model name")
    config_p.add_argument("--show", action="store_true", help="Show current config")
    config_p.add_argument("-h", "--help", action="store_true", help="Show help information")

    args = parser.parse_args()

    if not args.command:
        if args.help:
            _print_global_help()
        else:
            _print_global_help()
        return

    if args.command == "respond":
        if getattr(args, 'help', False):
            _print_respond_help()
        else:
            handle_respond(args)
    elif args.command == "chat":
        if getattr(args, 'help', False):
            _print_chat_help()
        elif args.set_default_model:
            set_default_model(args.set_default_model)
            render_text(f"Default model set to: {args.set_default_model}", "success")
        else:
            handle_chat(args)
    elif args.command == "token-count":
        if getattr(args, 'help', False):
            _print_token_count_help()
        else:
            handle_token_count(args)
    elif args.command == "schema":
        if getattr(args, 'help', False):
            _print_schema_help()
        else:
            handle_schema(args)
    elif args.command == "serve":
        if getattr(args, 'help', False):
            _print_serve_help()
        else:
            handle_serve(args)
    elif args.command == "available":
        handle_available(args)
    elif args.command == "quota-usage":
        handle_quota_usage(args)
    elif args.command == "config":
        handle_config(args)


# ═══════════════════════════════════════════════════════════════════════
# Help text — matches original fm output exactly
# ═══════════════════════════════════════════════════════════════════════

def _print_global_help():
    show_logo()
    print()
    print(f"  {GREEN_HEX}{BOLD}USAGE{RESET}")
    print(f"    {GRAY_HEX}%{RESET} fm {GRAY_HEX}<command> [options]{RESET}")
    print()
    print(f"  {GREEN_HEX}{BOLD}COMMANDS{RESET}")
    print(f"    {BOLD}respond       {RESET}Generate a response to a prompt")
    print(f"    {BOLD}chat          {RESET}Start an interactive chat session")
    print(f"    {BOLD}token-count   {RESET}Count tokens in a prompt or instructions")
    print(f"    {BOLD}schema        {RESET}Generate a JSON generation schema")
    print(f"    {BOLD}serve         {RESET}Start a Chat Completions API server")
    print(f"    {BOLD}available     {RESET}Check model availability")
    print(f"    {BOLD}quota-usage   {RESET}Check model quota usage")
    print()
    print(f"  {GREEN_HEX}{BOLD}MODELS{RESET}")
    print(f"    {BOLD}system        {RESET}On-device Apple Foundation Model {GRAY_HEX}(default){RESET}")
    print(f"    {BOLD}pcc           {RESET}Apple Foundation Model on Private Cloud Compute")
    print()
    print(f"  {GREEN_HEX}{BOLD}EXAMPLES{RESET}")
    print(f"    {GRAY_HEX}%{RESET} fm respond 'What is Swift?'")
    print(f"    {GRAY_HEX}%{RESET} fm respond --model pcc --stream 'Summarize this article'")
    print(f"    {GRAY_HEX}%{RESET} fm chat --instructions 'You are a coding assistant'")
    print(f"    {GRAY_HEX}%{RESET} fm token-count 'Hello world'")
    print(f"    {GRAY_HEX}%{RESET} fm schema object --name Person --string name --int age")
    print()
    print(f"  {ITALIC}{GRAY_HEX}Run 'fm <command> --help' for more information on a command.{RESET}")


def _print_respond_help():
    print(f"  {GREEN_HEX}{BOLD}fm respond{RESET}")
    print(f"  {GRAY_HEX}Generate a response to a prompt.{RESET}")
    print()
    print(f"  {GREEN_HEX}{BOLD}USAGE{RESET}")
    print(f"    {GRAY_HEX}%{RESET} fm respond 'What is Swift?'")
    print(f"    {GRAY_HEX}%{RESET} fm respond --model pcc 'What is Swift?'")
    print(f"    {GRAY_HEX}%{RESET} fm respond --use-case content-tagging 'Analyze this text'")
    print(f"    {GRAY_HEX}%{RESET} fm respond --image photo.jpg --text 'What is in this image?'")
    print(f"    {GRAY_HEX}%{RESET} echo 'What is Swift?' | fm respond")
    print()
    print(f"  {GREEN_HEX}{BOLD}ARGUMENTS{RESET}")
    print(f"    {BOLD}<prompt>                {RESET}Prompt for the model to respond to")
    print()
    print(f"  {GREEN_HEX}{BOLD}OPTIONS{RESET}")
    print(f"    {BOLD}-m, --model <model>     {RESET}Model to use (system, pcc)")
    print(f"    {BOLD}-i, --instructions <t>  {RESET}Instructions for the model to follow")
    print(f"    {BOLD}--schema <file>         {RESET}Path to a JSON schema file")
    print(f"    {BOLD}--text <text>           {RESET}Text segment to include in the prompt")
    print(f"    {BOLD}--image <path>          {RESET}Image file path to include in the prompt")
    print(f"    {BOLD}--load-transcript <f>   {RESET}Path to a saved transcript")
    print(f"    {BOLD}--save-transcript <n>   {RESET}Save transcript after responding")
    print(f"    {BOLD}--[no-]stream           {RESET}Stream the output as it's generated (default: on)")
    print(f"    {BOLD}-g, --greedy            {RESET}Use greedy sampling")
    print(f"    {BOLD}-v, --verbose           {RESET}Print verbose output")
    print(f"    {BOLD}-h, --help              {RESET}Show help information")
    print()
    print(f"  {GREEN_HEX}{BOLD}SYSTEM MODEL OPTIONS{RESET}")
    print(f"    {BOLD}--use-case <case>       {RESET}Model use case (general, content-tagging)")
    print(f"    {BOLD}--guardrails <level>    {RESET}Guardrail level (default, permissive-content-transformations)")
    print()
    print(f"  {GREEN_HEX}{BOLD}MODELS{RESET}")
    print(f"    {BOLD}system        {RESET}On-device Apple Foundation Model {GRAY_HEX}(default){RESET}")
    print(f"    {BOLD}pcc           {RESET}Apple Foundation Model on Private Cloud Compute")


def _print_chat_help():
    print(f"  {GREEN_HEX}{BOLD}fm chat{RESET}")
    print(f"  {GRAY_HEX}Start an interactive chat session.{RESET}")
    print()
    print(f"  {GREEN_HEX}{BOLD}USAGE{RESET}")
    print(f"    {GRAY_HEX}%{RESET} fm chat")
    print(f"    {GRAY_HEX}%{RESET} fm chat --resume my-session")
    print(f"    {GRAY_HEX}%{RESET} fm chat --instructions 'You are a helpful coding assistant'")
    print()
    print(f"  {GREEN_HEX}{BOLD}OPTIONS{RESET}")
    print(f"    {BOLD}-m, --model <model>     {RESET}Model to use (system, pcc)")
    print(f"    {BOLD}--set-default-model <m>  {RESET}Persist default model (system or pcc)")
    print(f"    {BOLD}-r, --resume <name>     {RESET}Resume a saved chat session")
    print(f"    {BOLD}--continue              {RESET}Continue the most recent chat session")
    print(f"    {BOLD}-i, --instructions <t>  {RESET}Instructions for the model")
    print(f"    {BOLD}-h, --help              {RESET}Show help information")
    print()
    print(f"  {ITALIC}{GRAY_HEX}Sessions are saved to ~/.fm-clone/sessions/ and can be resumed with --resume.{RESET}")


def _print_token_count_help():
    print(f"  {GREEN_HEX}{BOLD}fm token-count{RESET}")
    print(f"  {GRAY_HEX}Count the tokens in a prompt, instructions, or saved transcript.{RESET}")
    print()
    print(f"  {GREEN_HEX}{BOLD}USAGE{RESET}")
    print(f"    {GRAY_HEX}%{RESET} fm token-count 'What is Swift?'")
    print(f"    {GRAY_HEX}%{RESET} fm token-count -i 'You are a helpful assistant' 'What is Swift?'")
    print(f"    {GRAY_HEX}%{RESET} fm token-count -i 'Answer concisely'")
    print(f"    {GRAY_HEX}%{RESET} fm token-count --image photo.jpg --text 'Describe this image'")
    print(f"    {GRAY_HEX}%{RESET} echo 'What is Swift?' | fm token-count")
    print(f"    {GRAY_HEX}%{RESET} fm token-count --load-transcript session.json 'Follow up'")
    print()
    print(f"  {GREEN_HEX}{BOLD}ARGUMENTS{RESET}")
    print(f"    {BOLD}<prompt>                {RESET}Prompt to count tokens for")
    print()
    print(f"  {GREEN_HEX}{BOLD}OPTIONS{RESET}")
    print(f"    {BOLD}-i, --instructions <t>  {RESET}Instructions to include in the count")
    print(f"    {BOLD}--text <t>              {RESET}Additional text segment to include (repeatable)")
    print(f"    {BOLD}--image <path>          {RESET}Image to include in the prompt (repeatable)")
    print(f"    {BOLD}--load-transcript <f>   {RESET}Saved transcript to seed the count")
    print(f"    {BOLD}-q, --quiet             {RESET}Print only the integer count")
    print(f"    {BOLD}-h, --help              {RESET}Show help information")
    print()
    print(f"  {ITALIC}{GRAY_HEX}Only works with the on-device system model. Output is 'Token count: N' in a{RESET}")
    print(f"  {ITALIC}{GRAY_HEX}terminal and a bare integer when piped; use --quiet to force the bare form.{RESET}")


def _print_schema_help():
    print(f"  {GREEN_HEX}{BOLD}fm schema{RESET}")
    print(f"  {GRAY_HEX}Generate a JSON generation schema.{RESET}")
    print()
    print(f"  {GREEN_HEX}{BOLD}SUBCOMMANDS{RESET}")
    print(f"    {BOLD}object        {RESET}Generate a JSON schema for an object type")
    print()
    print(f"  {GREEN_HEX}{BOLD}EXAMPLES{RESET}")
    print(f"    {GRAY_HEX}%{RESET} fm schema object --name Person --string name --int age")
    print(f"    {GRAY_HEX}%{RESET} fm schema object --name Dog --string breed --boolean friendly")
    print()
    print(f"  {ITALIC}{GRAY_HEX}Run 'fm schema object --help' for detailed property declaration syntax.{RESET}")


def _print_serve_help():
    print(f"  {GREEN_HEX}{BOLD}fm serve{RESET}")
    print(f"  {GRAY_HEX}Start a Chat Completions API server for Foundation Models.{RESET}")
    print()
    print(f"  {GREEN_HEX}{BOLD}USAGE{RESET}")
    print(f"    {GRAY_HEX}%{RESET} fm serve")
    print(f"    {GRAY_HEX}%{RESET} fm serve --port 1976")
    print(f"    {GRAY_HEX}%{RESET} fm serve --host 0.0.0.0 --port 1976")
    print(f"    {GRAY_HEX}%{RESET} fm serve --socket /tmp/fm.sock")
    print()
    print(f"  {GREEN_HEX}{BOLD}OPTIONS{RESET}")
    print(f"    {BOLD}--host <host>           {RESET}Host address to bind to (TCP mode)")
    print(f"    {BOLD}--port <port>           {RESET}Port to listen on, 1-65535 (TCP mode)")
    print(f"    {BOLD}--socket <path>         {RESET}Unix domain socket path (socket mode)")
    print(f"    {BOLD}-h, --help              {RESET}Show help information")
    print()
    print(f"  {GREEN_HEX}{BOLD}ENDPOINTS{RESET}")
    print(f"    {BOLD}POST /v1/chat/completions{RESET}Chat completions (streaming & non-streaming)")
    print(f"    {BOLD}GET  /v1/models         {RESET}List available models")
    print(f"    {BOLD}GET  /health            {RESET}Health check")
    print()
    print(f"  {GREEN_HEX}{BOLD}MODELS{RESET}")
    print(f"    {BOLD}system        {RESET}On-device Apple Foundation Model {GRAY_HEX}(default){RESET}")
    print(f"    {BOLD}pcc           {RESET}Apple Foundation Model on Private Cloud Compute")
    print()
    print(f"  {ITALIC}{GRAY_HEX}Use --socket for Unix domain socket transport (recommended for local Python bindings).{RESET}")


# ═══════════════════════════════════════════════════════════════════════
# Command handlers
# ═══════════════════════════════════════════════════════════════════════

def handle_respond(args):
    prompt = args.prompt or sys.stdin.read().strip()
    if not prompt:
        render_error("Error: No prompt provided.")
        return

    if args.load_transcript:
        transcript = Transcript.load(args.load_transcript)
    else:
        transcript = Transcript(instructions=args.instructions)

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

    temperature = 0.0 if args.greedy else 0.7
    images = args.image or []

    if args.stream:
        start_stream()
        full = ""
        try:
            for chunk in chat_completion(
                messages, stream=True, schema=schema, temperature=temperature,
                model=args.model, guardrails=args.guardrails, use_case=args.use_case,
                images=images,
            ):
                full += chunk
                stream_chunk(full)
            end_stream()
            print()
        except Exception as e:
            end_stream()
            render_error(f"Error: {e}")
            return
    else:
        try:
            result = chat_completion(
                messages, stream=False, schema=schema, temperature=temperature,
                model=args.model, guardrails=args.guardrails, use_case=args.use_case,
                images=images,
            )
            render_markdown(result)
        except Exception as e:
            render_error(f"Error: {e}")
            return
        full = result

    if args.save_transcript:
        transcript.add_response(full)
        transcript.save(args.save_transcript)
        render_text(f"Transcript saved: {args.save_transcript}", "dim")


def handle_chat(args):
    run_chat(
        instructions=args.instructions,
        resume=args.resume,
        model=args.model,
        continue_session=args.continue_session,
    )


def handle_token_count(args):
    text = args.prompt or sys.stdin.read().strip()
    if args.instructions:
        text = f"{args.instructions}\n\n{text}"
    if args.text:
        text = "\n".join(args.text) + "\n" + text

    image_count = 0
    if args.image:
        for img in args.image:
            image_count += image_token_count(img)

    if args.load_transcript:
        try:
            transcript = Transcript.load(args.load_transcript)
            messages = transcript.get_messages_for_api()
            text = json.dumps(messages)
        except Exception as e:
            render_error(f"Failed to load transcript: {e}")
            return

    count = count_tokens(text) + image_count
    if args.quiet or not sys.stdout.isatty():
        print(count)
    else:
        print(f"Token count: {count}")


def handle_schema(args):
    if args.schema_command != "object":
        render_error("Use: fm schema object --name <name> [--string <prop> ...]")
        return

    properties = []
    for name in (args.string or []):
        properties.append(SchemaProperty(name, "string"))
    for name in (args.integer or []):
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
    render_text(f"Starting fm API server on {args.host}:{args.port}", "info")
    render_text("Endpoints:", "dim")
    render_text("  POST /v1/chat/completions", "dim")
    render_text("  GET  /v1/models", "dim")
    render_text("  GET  /health", "dim")
    print()
    run_server(host=args.host, port=args.port, socket_path=args.socket_path)


def handle_available(args):
    # Check system model
    sys_result = check_availability("system")
    if sys_result["available"]:
        render_text(f"  System model available: {sys_result['model']}", "success")
        render_text(f"  Provider: {sys_result['provider']}", "dim")
    else:
        render_error(f"  System model unavailable: {sys_result.get('error', 'Unknown error')}")

    # Check pcc model
    pcc_result = check_availability("pcc")
    if pcc_result["available"]:
        render_text(f"  PCC model available: {pcc_result['model']}", "success")
        render_text(f"  Provider: {pcc_result['provider']}", "dim")
    else:
        render_error(f"  PCC model unavailable: {pcc_result.get('error', 'Unknown error')}")


def handle_quota_usage(args):
    sys_cfg = get_api_config("system")
    pcc_cfg = get_api_config("pcc")
    print(f"System: {GRAY_HEX}Model: {sys_cfg['model']} @ {sys_cfg['base_url']}{RESET}")
    print(f"PCC:    {GRAY_HEX}Model: {pcc_cfg['model']} @ {pcc_cfg['base_url']}{RESET}")


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
