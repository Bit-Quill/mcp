# Amazon ElastiCache/MemoryDB Valkey MCP Server

An AWS Labs Model Context Protocol (MCP) server for Amazon ElastiCache [Valkey](https://valkey.io/) datastores.

## Features

This MCP server provides 12 purpose-built tools for AI agents working with Valkey. The tool surface is designed to minimize token costs and agent error rates by accepting structured JSON input and handling command translation internally.

### Valkey AI Search — 4 tools

| Tool | What It Does |
|------|-------------|
| `manage_index` | Create, drop, inspect, or list search indices. Accepts structured schema definitions with TEXT, NUMERIC, TAG, and VECTOR fields. Defaults to COSINE distance + HNSW algorithm. |
| `add_documents` | Ingest documents with optional embedding generation. Supports Bedrock, OpenAI, and Ollama providers. Auto-creates the index if missing. |
| `search` | Unified semantic, text, hybrid, and find-similar search. Auto-detects mode from parameters, or accepts an explicit `mode` override. |
| `aggregate` | Structured pipeline builder for FT.AGGREGATE. Supports GROUPBY, SORTBY, APPLY, FILTER, and LIMIT stages with 12 REDUCE functions. |

### Valkey JSON Intelligence — 5 tools

| Tool | What It Does |
|------|-------------|
| `json_get` | Get a JSON value at a path from a Valkey key. |
| `json_set` | Set a JSON value at a path with optional TTL. |
| `json_arrappend` | Append values to a JSON array at a path. |
| `json_arrpop` | Pop an element from a JSON array at a path. |
| `json_arrtrim` | Trim a JSON array to a specified range. |

### Valkey Command Runner — 3 tools (3-tier safety)

| Tool | Tier | What It Does |
|------|------|-------------|
| `valkey_read` | Safe | Read-only commands (GET, HGETALL, SCAN, INFO, etc.). Always available, even in readonly mode. |
| `valkey_write` | Write | Mutating commands (SET, HSET, DEL, LPUSH, etc.). Destructive commands blocked. Disabled in readonly mode. |
| `valkey_admin` | Admin | Destructive commands (FLUSHALL, CONFIG SET, EVAL, etc.). Disabled by default — requires `VALKEY_ADMIN_ENABLED=true` + `confirm=True`. |

**3-tier safety model:** `valkey_read` (always safe) → `valkey_write` (mutations, no destructive) → `valkey_admin` (opt-in only, disabled by default). An agent cannot accidentally FLUSHALL a staging cluster.

### Additional Features

- **Valkey-GLIDE**: Built on [Valkey GLIDE](https://github.com/valkey-io/valkey-glide) for async-native performance.
- **Cluster Support**: Standalone and clustered Valkey deployments.
- **SSL/TLS Security**: Secure connections via TLS.
- **Readonly Mode**: Prevent write operations with `--readonly`.
- **Multi-provider Embeddings**: Bedrock, OpenAI, Ollama, with automatic fallback.

## Prerequisites

1. Install `uv` from [Astral](https://docs.astral.sh/uv/getting-started/installation/)
2. Install Python using `uv python install 3.10`
3. Access to a Valkey datastore (with search module for AI Search tools, JSON module for JSON tools).
4. For Amazon ElastiCache/MemoryDB connection instructions, see [ELASTICACHECONNECT.md](ELASTICACHECONNECT.md).

## Installation

| Kiro | Cursor | VS Code |
|:----:|:------:|:-------:|
| [![Add to Kiro](https://kiro.dev/images/add-to-kiro.svg)](https://kiro.dev/launch/mcp/add?name=awslabs.valkey-mcp-server&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22awslabs.valkey-mcp-server%40latest%22%5D%2C%22env%22%3A%7B%22VALKEY_HOST%22%3A%22127.0.0.1%22%2C%22VALKEY_PORT%22%3A%226379%22%2C%22FASTMCP_LOG_LEVEL%22%3A%22ERROR%22%7D%7D) | [![Install MCP Server](https://cursor.com/deeplink/mcp-install-light.svg)](https://cursor.com/en/install-mcp?name=awslabs.valkey-mcp-server&config=eyJjb21tYW5kIjoidXZ4IGF3c2xhYnMudmFsa2V5LW1jcC1zZXJ2ZXJAbGF0ZXN0IiwiZW52Ijp7IlZBTEtFWV9IT1NUIjoiMTI3LjAuMC4xIiwiVkFMS0VZX1BPUlQiOiI2Mzc5IiwiRkFTVE1DUF9MT0dfTEVWRUwiOiJFUlJPUiJ9LCJhdXRvQXBwcm92ZSI6W10sImRpc2FibGVkIjpmYWxzZX0%3D) | [![Install on VS Code](https://img.shields.io/badge/Install_on-VS_Code-FF9900?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=Valkey%20MCP%20Server&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22awslabs.valkey-mcp-server%40latest%22%5D%2C%22env%22%3A%7B%22VALKEY_HOST%22%3A%22127.0.0.1%22%2C%22VALKEY_PORT%22%3A%226379%22%2C%22FASTMCP_LOG_LEVEL%22%3A%22ERROR%22%7D%2C%22autoApprove%22%3A%5B%5D%2C%22disabled%22%3Afalse%7D) |

### MCP Configuration

```json
{
  "mcpServers": {
    "awslabs.valkey-mcp-server": {
      "command": "uvx",
      "args": ["awslabs.valkey-mcp-server@latest"],
      "env": {
        "VALKEY_HOST": "127.0.0.1",
        "VALKEY_PORT": "6379",
        "EMBEDDING_PROVIDER": "ollama",
        "OLLAMA_HOST": "http://localhost:11434",
        "FASTMCP_LOG_LEVEL": "ERROR"
      }
    }
  }
}
```

Readonly mode (disables all write operations):

```json
{
  "mcpServers": {
    "awslabs.valkey-mcp-server": {
      "command": "uvx",
      "args": ["awslabs.valkey-mcp-server@latest", "--readonly"],
      "env": {
        "VALKEY_HOST": "127.0.0.1",
        "VALKEY_PORT": "6379",
        "FASTMCP_LOG_LEVEL": "ERROR"
      }
    }
  }
}
```

### Docker

```json
{
  "mcpServers": {
    "awslabs.valkey-mcp-server": {
      "command": "docker",
      "args": [
        "run", "--rm", "--interactive",
        "--env", "FASTMCP_LOG_LEVEL=ERROR",
        "--env", "VALKEY_HOST=127.0.0.1",
        "--env", "VALKEY_PORT=6379",
        "awslabs/valkey-mcp-server:latest"
      ]
    }
  }
}
```

## Configuration

### Valkey Connection

| Variable | Description | Default |
|----------|-------------|---------|
| `VALKEY_HOST` | Valkey hostname or IP | `127.0.0.1` |
| `VALKEY_PORT` | Valkey port | `6379` |
| `VALKEY_USERNAME` | Username for authentication | `None` |
| `VALKEY_PWD` | Password for authentication | `""` |
| `VALKEY_USE_SSL` | Enable TLS | `false` |
| `VALKEY_SSL_CA_PATH` | CA certificate path | `None` |
| `VALKEY_SSL_KEYFILE` | Client private key file | `None` |
| `VALKEY_SSL_CERTFILE` | Client certificate file | `None` |
| `VALKEY_SSL_CERT_REQS` | Certificate verification mode | `required` |
| `VALKEY_SSL_CA_CERTS` | Trusted CA certificates path | `None` |
| `VALKEY_CLUSTER_MODE` | Enable cluster mode | `false` |
| `VALKEY_ADMIN_ENABLED` | Enable admin tier (destructive commands) | `false` |

### Embeddings Provider

Embedding generation is required for semantic search in `add_documents` and `search` tools.

| Variable | Description | Default |
|----------|-------------|---------|
| `EMBEDDING_PROVIDER` | Provider: `bedrock`, `openai`, `ollama`, or `hash` | `bedrock` |

#### Bedrock

Credentials via `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`, `AWS_PROFILE`, or IAM role.

| Variable | Description | Default |
|----------|-------------|---------|
| `AWS_REGION` | AWS region | `us-east-1` |
| `BEDROCK_MODEL_ID` | Model ID | `amazon.nova-2-multimodal-embeddings-v1:0` |
| `BEDROCK_NORMALIZE` | Normalize embeddings | `None` |
| `BEDROCK_DIMENSIONS` | Embedding dimensions | `None` (model default) |
| `BEDROCK_INPUT_TYPE` | Input type | `None` |
| `BEDROCK_MAX_ATTEMPTS` | Max retry attempts | `3` |
| `BEDROCK_MAX_POOL_CONNECTIONS` | Connection pool size | `50` |
| `BEDROCK_RETRY_MODE` | Retry mode | `adaptive` |

#### OpenAI

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | API key (required) | `None` |
| `OPENAI_MODEL` | Model name | `text-embedding-3-small` |

#### Ollama

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_HOST` | Ollama endpoint URL | `http://localhost:11434` |
| `OLLAMA_EMBEDDING_MODEL` | Model name | `nomic-embed-text` |

## Example Usage

```
"Create a search index for product data with title, category, price, and embedding fields"
"Add these product documents and generate embeddings from the title field"
"Search for products similar to 'wireless headphones'"
"Find products similar to product:123"
"Show me the average price by category"
"Store this JSON config and set a 1-hour TTL"
"Get the nested value at $.settings.theme from the config key"
```

## Development

### Running Tests

```bash
uv venv && source .venv/bin/activate && uv sync

# Unit tests
uv run --frozen pytest tests/ -m "not live and not integration"

# Live integration tests (requires VALKEY_HOST and EMBEDDING_PROVIDER)
uv run --frozen pytest tests/test_search_live.py -m live -v
```

### Building Docker Image

```bash
docker build -t awslabs/valkey-mcp-server .
```
