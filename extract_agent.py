"""
Export a Foundry Agent Service agent's definition as YAML.

Writes the agent-version definition (metadata, instructions, model, tools, ...)
in the same shape as the Foundry portal's exported agent YAML.

Auth: DefaultAzureCredential (run `az login` first).

Configuration is read from a .env file (or environment variables):
  FOUNDRY_PROJECT_ENDPOINT  (required)  e.g. https://<acct>.services.ai.azure.com/api/projects/<project>
  FOUNDRY_AGENT_NAME        (optional)  default agent name if --agent is omitted

Usage:
  python extract_agent.py --agent RoamingAgent     # YAML to stdout
  python extract_agent.py --version 10             # or 'latest' (default)
  python extract_agent.py --out RoamingAgent.yaml  # write YAML to a file
"""

from __future__ import annotations

import argparse
import os
from typing import Any

import yaml
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

load_dotenv()

# Configuration comes from the environment (.env). Keep these project-agnostic.
PROJECT_ENDPOINT = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
DEFAULT_AGENT_NAME = os.getenv("FOUNDRY_AGENT_NAME")

# Key ordering to mirror the exported agent-version YAML.
_TOP_ORDER = [
    "metadata", "object", "id", "name", "version", "description",
    "created_at", "definition", "status", "instance_identity", "blueprint",
    "blueprint_reference", "agent_guid",
]
_DEF_ORDER = ["kind", "model", "instructions", "reasoning", "tools"]


def to_dict(obj: Any) -> Any:
    """Best-effort conversion of an SDK model to a plain, YAML-able value."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_dict(v) for v in obj]
    for method in ("as_dict", "to_dict"):
        fn = getattr(obj, method, None)
        if callable(fn):
            try:
                return to_dict(fn())
            except Exception:
                pass
    if hasattr(obj, "__dict__"):
        return {k: to_dict(v) for k, v in vars(obj).items() if not k.startswith("_")}
    return str(obj)


def get_version_node(agent: Any) -> dict:
    """Return the full agent-version node (metadata, definition, identity, ...)."""
    raw = to_dict(agent)
    if not isinstance(raw, dict):
        return {"raw": raw}
    versions = raw.get("versions")
    if isinstance(versions, dict):
        node = versions.get("latest") or next(
            (v for v in versions.values() if isinstance(v, dict)), None
        )
        if isinstance(node, dict):
            return node
    return raw


class _AgentDumper(yaml.SafeDumper):
    """SafeDumper that renders multi-line strings as literal blocks (``|``)."""


_AgentDumper.add_representer(
    str,
    lambda dumper, data: dumper.represent_scalar(
        "tag:yaml.org,2002:str", data, style="|" if "\n" in data else None
    ),
)


def _ordered(d: dict, order: list[str]) -> dict:
    """Return a copy of ``d`` with ``order`` keys first, then the rest."""
    return {**{k: d[k] for k in order if k in d}, **d}


def to_yaml(version_node: dict) -> str:
    node = _ordered(version_node, _TOP_ORDER)
    if isinstance(node.get("definition"), dict):
        node["definition"] = _ordered(node["definition"], _DEF_ORDER)
    return yaml.dump(
        node,
        Dumper=_AgentDumper,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=100,
    )


def resolve_agent(client: AIProjectClient, name: str, version: str | None) -> Any:
    """Fetch an agent by name, optionally pinned to a version (else latest)."""
    agents = client.agents

    # "latest"/empty means "no specific version".
    if version is not None and str(version).strip().lower() in ("latest", "@latest", ""):
        version = None

    if version is not None:
        for getter in ("get_version", "get_agent_version"):
            fn = getattr(agents, getter, None)
            if callable(fn):
                for call in (lambda: fn(agent_name=name, version=version),
                             lambda: fn(name, version)):
                    try:
                        return call()
                    except Exception:
                        pass

    for getter in ("get", "get_agent"):
        fn = getattr(agents, getter, None)
        if callable(fn):
            for call in (lambda: fn(agent_name=name), lambda: fn(name)):
                try:
                    return call()
                except Exception:
                    pass

    # Fall back to listing and matching by name (latest match wins).
    for lister in ("list", "list_agents", "list_versions"):
        fn = getattr(agents, lister, None)
        if callable(fn):
            try:
                matches = [a for a in fn() if getattr(a, "name", None) == name]
                if matches:
                    return matches[-1]
            except Exception:
                pass

    raise RuntimeError(f"Could not retrieve agent '{name}'.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a Foundry agent as YAML.")
    parser.add_argument("--agent", default=DEFAULT_AGENT_NAME,
                        help="Agent name (default: FOUNDRY_AGENT_NAME from .env).")
    parser.add_argument("--version", default=None,
                        help="Agent version, or 'latest' (default: latest).")
    parser.add_argument("--endpoint", default=PROJECT_ENDPOINT,
                        help="Foundry project endpoint "
                             "(default: FOUNDRY_PROJECT_ENDPOINT from .env).")
    parser.add_argument("--out", default=None,
                        help="Path to write the YAML to (default: stdout).")
    args = parser.parse_args()

    if not args.endpoint:
        parser.error("No project endpoint. Set FOUNDRY_PROJECT_ENDPOINT in .env "
                     "or pass --endpoint.")
    if not args.agent:
        parser.error("No agent name. Set FOUNDRY_AGENT_NAME in .env or pass --agent.")

    with AIProjectClient(endpoint=args.endpoint,
                         credential=DefaultAzureCredential()) as client:
        agent = resolve_agent(client, args.agent, args.version)
        output = to_yaml(get_version_node(agent))

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(output)
        print(f"Wrote agent-version YAML to {args.out}")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()

