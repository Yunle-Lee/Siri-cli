# fm-clone

Open-source reimplementation of Apple's **Foundation Models CLI** (`fm`) from macOS 27.

## Original vs Clone

| | Apple `fm` (`/usr/bin/fm`) | This clone (`fm-clone`) |
|---|---|---|
| **Model backend** | `FoundationModels.framework` (private) | OpenAI-compatible API |
| **`system` model** | On-device Apple `instruct_3b` (~3B params), built into macOS | Configurable: point to any local model server |
| **`pcc` model** | Apple Private Cloud Compute | Configurable: point to any cloud API |
| **Image input** | Native multimodal encoder | Base64 via OpenAI vision API |
| **CLI interface** | Original | 1:1 replica |
| **Availability** | macOS 27+ only | Any OS with Python 3.10+ |

The original `fm` uses Apple's private `FoundationModels.framework`, which includes a ~3B parameter instruction-tuned model (asset ID: `com.apple.fm.language.instruct_3b`) and a tokenizer bundled directly in macOS 27. These are **not extractable** — this clone cannot use them.

Instead, this clone connects to **any OpenAI-compatible API**, giving you full control over which model powers each mode.

## Installation

```bash
git clone https://github.com/Yunle-Lee/Siri-cli.git
cd Siri-cli
pip install -r requirements.txt
```

## Dual-model setup (matching original `system` / `pcc`)

The original `fm` has two models:
- **`system`** — local on-device model
- **`pcc`** — cloud model via Private Cloud Compute

This clone maps them to two independently configurable backends:

### Option A: Local model as `system`, cloud API as `pcc`

```bash
# 1. Start a local model server (pick one):

# Ollama (recommended):
ollama serve
ollama pull llama3.2:3b      # ~3B, matches original size

# LM Studio:
# Launch LM Studio → start local server on port 1234

# 2. Configure fm-clone:
fm config --set-system-url http://localhost:11434/v1     # Ollama
fm config --set-system-model llama3.2:3b

fm config --set-pcc-url https://api.openai.com/v1        # Cloud API
fm config --set-pcc-model gpt-4o-mini
fm config --set-api-key sk-your-key-here

# 3. Use both:
fm respond --model system 'What is Swift?'   # → local Ollama
fm respond --model pcc 'Summarize this...'   # → cloud OpenAI
```

### Option B: Single backend (default)

If you only configure one backend, both `system` and `pcc` use it:

```bash
export FM_API_KEY=sk-your-key
export FM_API_BASE=https://api.openai.com/v1
fm respond 'Hello'          # both models go to OpenAI
```

## Quick Start

```bash
# Configure
fm config --set-api-key sk-your-key-here
fm config --set-base-url https://api.openai.com/v1
fm config --set-model gpt-4o-mini

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
| `fm respond` | Single prompt → response (streaming, schema, images, guardrails) |
| `fm chat` | Interactive REPL chat with session management |
| `fm token-count` | Count tokens in a prompt or transcript |
| `fm schema` | Generate JSON schema for structured output |
| `fm serve` | Start OpenAI-compatible Chat Completions API server |
| `fm available` | Check model/API availability |
| `fm quota-usage` | Show quota information |

## Chat REPL Commands

Inside `fm chat`, use `/`-prefixed commands:

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/instructions [text]` | Set or view system instructions |
| `/model <system\|pcc>` | Switch between local and cloud models |
| `/save [name]` | Save current session |
| `/load <name>` | Load a saved session |
| `/history` | List saved sessions |
| `/clear` | Start a new session |
| `/appearance <dark\|light\|auto>` | Set terminal color scheme |
| `/quit`, `/exit` | Exit chat |

## Serve Mode

Start an OpenAI-compatible API server:

```bash
fm serve --host 0.0.0.0 --port 8080

# Unix socket mode (for local Python bindings)
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
fm config --set-system-url http://localhost:11434/v1
fm config --set-system-model llama3.2:3b
fm config --set-pcc-url https://api.openai.com/v1
fm config --set-pcc-model gpt-4o
fm config --show
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `FM_API_KEY` | API key (overrides config) |
| `FM_API_BASE` | Default API base URL |
| `FM_MODEL` | Default model name |
| `FM_SYSTEM_URL` | Base URL for `system` model |
| `FM_SYSTEM_MODEL` | Model name for `system` |
| `FM_PCC_URL` | Base URL for `pcc` model |
| `FM_PCC_MODEL` | Model name for `pcc` |
| `OPENAI_API_KEY` | Fallback API key |

## Sessions

Chat sessions are saved to `~/.fm-clone/sessions/` in a JSON format compatible with Apple's transcript structure (version 1.1).

## License

MIT
