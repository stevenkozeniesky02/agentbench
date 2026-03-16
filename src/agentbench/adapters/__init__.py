"""Agent adapters for AgentBench."""

from agentbench.adapters.base import AgentAdapter
from agentbench.adapters.manual import ManualAdapter
from agentbench.adapters.claude_code import ClaudeCodeAdapter

ADAPTERS: dict[str, type[AgentAdapter]] = {
    "manual": ManualAdapter,
    "claude": ClaudeCodeAdapter,
}

__all__ = ["AgentAdapter", "ManualAdapter", "ClaudeCodeAdapter", "ADAPTERS"]
