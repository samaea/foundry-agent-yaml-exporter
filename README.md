# Foundry Agent YAML Exporter Sample

A small Python utility that exports an **Azure AI Foundry Agent Service** agent's
definition to YAML, in the same shape as the definition you see in the Foundry
portal.

For a given agent it captures:

- **Instructions** (system prompt) as a readable literal block
- **Model** and **reasoning** settings
- **Tools** — MCP servers, Azure AI Search indexes, knowledge bases, etc., with
  their endpoints / connection references
- The surrounding **agent-version metadata** (id, version, status, identity,
  blueprint, ...)

The output mirrors the portal's exported agent YAML, so it's handy for source
control, review, diffing versions, or moving a definition between projects.

## Requirements

- Python 3.9+
- An Azure identity with access to the Foundry project
  ([`DefaultAzureCredential`](https://learn.microsoft.com/python/api/overview/azure/identity-readme) —
  e.g. run `az login`, or use a managed identity / service principal)

## Setup

```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Sign in (any DefaultAzureCredential source works)
az login

# 3. Configure your project (copy the template and fill it in)
copy .env.example .env
```

Edit `.env`:

```dotenv
# Foundry project endpoint: https://<account>.services.ai.azure.com/api/projects/<project>
FOUNDRY_PROJECT_ENDPOINT=https://<account>.services.ai.azure.com/api/projects/<project>

# Default agent name used when --agent is not supplied (optional).
FOUNDRY_AGENT_NAME=<AgentName>
```

`.env` is git-ignored, so your project-specific values never get committed.

## Usage

Print the latest version of the default agent (from `.env`) to the screen:

```powershell
python extract_agent.py
```

Write it to a YAML file:

```powershell
python extract_agent.py --out MyAgent.yaml
```

Target a specific agent and/or version:

```powershell
python extract_agent.py --agent RoamingAgent --version 10 --out RoamingAgent.yaml
```

Override the endpoint from the command line (instead of `.env`):

```powershell
python extract_agent.py --endpoint https://<account>.services.ai.azure.com/api/projects/<project> --agent MyAgent
```

### Options

| Option       | Description                                                        | Default                              |
| ------------ | ------------------------------------------------------------------ | ------------------------------------ |
| `--agent`    | Agent name to export.                                              | `FOUNDRY_AGENT_NAME` from `.env`     |
| `--version`  | Specific version number, or `latest`.                             | `latest`                             |
| `--endpoint` | Foundry project endpoint.                                          | `FOUNDRY_PROJECT_ENDPOINT` from `.env` |
| `--out`      | File path to write the YAML to. If omitted, prints to stdout.      | stdout                               |

## Example output

```yaml
object: agent.version
id: RoamingAgent:10
name: RoamingAgent
version: '10'
definition:
  kind: prompt
  model: gpt-5.1
  instructions: |
    You are **RoamingAgent**, a virtual assistant for a mobile telecommunications
    operator. ...
  reasoning:
    effort: low
  tools:
  - type: mcp
    server_label: roaming-mcp-dev-tool
    server_url: https://<func-app>.azurewebsites.net/runtime/webhooks/mcp
    require_approval: never
    project_connection_id: roaming-mcp-dev-tool
  - type: azure_ai_search
    azure_ai_search:
      indexes:
      - project_connection_id: /subscriptions/.../connections/<connection>
        index_name: sales-index
        query_type: simple
        top_k: 5
status: active
```

## How it works

1. Loads configuration from `.env` (via `python-dotenv`).
2. Connects to the project with `AIProjectClient` and
   `DefaultAzureCredential`.
3. Resolves the requested agent/version (falling back gracefully across
   `azure-ai-projects` SDK method variations).
4. Normalizes the SDK model into plain Python and renders it with a custom YAML
   dumper that preserves key order and writes multi-line instructions as literal
   block scalars.

## Notes

- Azure AI Search indexes are referenced by their connection ID (as stored in
  the definition), not by a raw service URL — the search host is resolved at
  runtime via that connection.
- Authentication uses `DefaultAzureCredential`; no keys or secrets are stored by
  this tool.

## License

MIT
