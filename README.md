# fm-clone

An open-source reimplementation of Apple's **Foundation Models CLI** (`fm`) from macOS 27.

`fm` is a command-line tool for interacting with language models. This clone supports any **OpenAI-compatible API** (OpenAI, Ollama, vLLM, LiteLLM, Groq, Together AI, etc.) as the backend, while preserving the same CLI interface and session management.

## Installation

```bash
git clone https://github.com/Yunle-Lee/Siri-cli.git
cd Siri-cli
pip install -r requirements.txt
```

## Quick Start

```bash
# Configure your API
fm config --set-api-key sk-your-key-here
fm config --set-base-url https://api.openai.com/v1    # default
fm config --set-model gpt-4o-mini                     # default

# Or use environment variables
export FM_API_KEY=sk-your-key
export FM_API_BASE=https://api.openai.com/v1

# Ask a single question
fm respond 'What is Swift?'

# Start an interactive chat
fm chat --instructions 'You are a coding assistant'

# Count tokens
fm token-count 'Hello world'

# Generate JSON schema for structured output
fm schema object --name Person --string name --int age

# Start an OpenAI-compatible API server
fm serve --port 8080
```

## Commands

| Command | Description |
|---------|-------------|
| `respond` | Single prompt → response (with streaming, schema, images) |
| `chat` | Interactive REPL chat session |
| `token-count` | Count tokens in a prompt |
| `schema` | Generate JSON schema for structured output |
| `serve` | Start Chat Completions API server (OpenAI-compatible) |
| `available` | Check model/API availability |
| `quota-usage` | Show quota information |
| `config` | Manage API keys, base URL, model settings |

## Chat REPL Commands

Inside `fm chat`, use `/`-prefixed commands:

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/instructions [text]` | Set or view system instructions |
| `/model <name>` | Switch model |
| `/save [name]` | Save current session |
| `/load <name>` | Load a saved session |
| `/history` | List saved sessions |
| `/clear` | Start new session |
| `/quit`, `/exit` | Exit chat |

## Serve Mode

Start an OpenAI-compatible API server:

```bash
fm serve --host 0.0.0.0 --port 8080

# Unix socket mode (for local clients)
fm serve --socket /tmp/fm.sock
```

Endpoints:
- `POST /v1/chat/completions` — Chat completions (streaming & non-streaming)
- `GET /v1/models` — List available models
- `GET /health` — Health check

## Schema Builder

Generate JSON schemas for structured output:

```bash
# Simple object
fm schema object --name Person --string name --int age --boolean active

# Nested objects
fm schema object --name Restaurant --string title \
  --object address --schema "$(fm schema object --name Address --string street --string zipcode)"

# Union types
fm schema object --name SearchResult --anyOf \
  --schema "$(fm schema object --name Found --string name)" \
  --schema "$(fm schema object --name NotFound --string reason)"
```

## Configuration

Config stored in `~/.fm-clone/config`:

```bash
fm config --set-api-key sk-xxx
fm config --set-base-url https://api.openai.com/v1
fm config --set-model gpt-4o-mini
fm config --show
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `FM_API_KEY` | API key (overrides config) |
| `FM_API_BASE` | API base URL (overrides config) |
| `FM_MODEL` | Default model name (overrides config) |
| `OPENAI_API_KEY` | Fallback API key |

## Sessions

Chat sessions are saved to `~/.fm-clone/sessions/` in a JSON format compatible with Apple's transcript structure.

## License

MIT
