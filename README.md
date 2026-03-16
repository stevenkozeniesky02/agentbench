# AgentBench

**Standardized benchmark framework for comparing AI coding agents.**

<!-- Badges -->
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Status: Alpha](https://img.shields.io/badge/status-alpha-orange)

---

## Why Benchmark AI Coding Agents?

AI coding agents -- Claude Code, Codex CLI, Gemini CLI, Aider, and others -- are proliferating fast. But there is no standardized way to answer the question: **which one actually writes better code?**

Marketing benchmarks are self-reported and cherry-picked. Vibes-based comparisons don't scale. AgentBench fills this gap with reproducible, scored challenges that measure what matters: does the code build, do the tests pass, is it well-structured, and how long did it take?

Every agent gets the same prompt. Every result is scored with the same rubric. The output is a head-to-head comparison you can actually trust.

## Quick Start

### Install

```bash
# Clone the repository
git clone https://github.com/stevenkozeniesky02/agentbench.git
cd agentbench

# Install in development mode
pip install -e ".[dev]"
```

### Run a Single Challenge

```bash
agentbench run --agent claude-code --challenge easy/password-gen
```

### Run an Entire Tier

```bash
agentbench run --agent claude-code --tier easy
agentbench run --agent codex --tier easy
```

### Compare Results

```bash
agentbench compare results/claude-code.json results/codex.json
```

### Generate a Markdown Report

```bash
agentbench report results/ --output comparison.md
```

### List Available Challenges

```bash
agentbench list
```

## Architecture

```
agentbench/
  challenges/           # YAML challenge definitions
    easy/
    medium/
    hard/
  src/agentbench/
    models.py           # Immutable data models (frozen dataclasses)
    loader.py           # YAML challenge loader and discovery
    cli.py              # Click CLI with rich output
    report.py           # JSON/Markdown report generation
    metrics/            # Scoring subsystem
      build.py          # Build verification
      tests.py          # Test runner
      coverage.py       # Coverage measurement
      quality.py        # Code quality (cyclomatic complexity)
    adapters/           # Agent integrations
      base.py           # Abstract adapter interface
  examples/             # Sample results and reports
  tests/                # Test suite
```

The design follows a clean pipeline:

1. **Load** challenge definitions from YAML
2. **Execute** the challenge prompt through an agent adapter
3. **Measure** build success, test results, coverage, and code quality
4. **Score** using a weighted rubric (0-100 per challenge)
5. **Report** results as JSON, rich terminal tables, or Markdown

All data models are frozen dataclasses. No mutation anywhere in the pipeline.

## Challenge Tiers

| Tier | Difficulty | Typical Scope | Time Limit |
|------|-----------|---------------|-----------|
| **Easy** | Junior developer tasks | Single-module CLI tools, CRUD APIs, parsers | 30 min |
| **Medium** | Mid-level projects | Multi-module systems, database integration, auth | 60 min |
| **Hard** | Senior-level architecture | Distributed systems, complex algorithms, full-stack apps | 120 min |

Each tier tests progressively more sophisticated skills: code organization, error handling, testing discipline, and architectural thinking.

## Scoring Methodology

Each challenge produces a score from 0 to 100, computed as a weighted sum:

```
Score = Build(25) + Tests(20) + Coverage(15) + Quality(15) + Completeness(15) + Efficiency(10)
```

### Component Breakdown

| Component | Max Points | How It's Calculated |
|-----------|----------:|---------------------|
| **Build Success** | 25 | Binary: does the project build without errors? |
| **Test Pass Rate** | 20 | `20 * (tests_passed / tests_total)` |
| **Test Coverage** | 15 | `15 * line_coverage_ratio` (0.0 to 1.0) |
| **Code Quality** | 15 | Based on average cyclomatic complexity (lower is better) |
| **Completeness** | 15 | `15 * (expected_files_found / expected_files_total)` |
| **Efficiency** | 10 | `10 * max(0, 1.0 - time_seconds / 1800)` |

**Quality scoring thresholds:**

| Avg Cyclomatic Complexity | Quality Score |
|--------------------------:|--------------:|
| < 5 | 1.0 (full marks) |
| 5 - 9 | 0.5 |
| 10 - 19 | 0.2 |
| >= 20 | 0.0 |

The **aggregate score** for a run is the arithmetic mean across all challenges.

## Adding Custom Challenges

Create a YAML file in the appropriate tier directory:

```yaml
# challenges/easy/my-challenge.yaml

name: "My Custom Challenge"
language: python
time_limit_minutes: 30

prompt: |
  Build a command-line tool that does X.

  Requirements:
  - Requirement one
  - Requirement two
  - Write unit tests covering core functionality

expected_files:
  - pyproject.toml
  - src/my_tool/main.py
  - tests/test_main.py

setup_commands:
  - python -m pip install -e ".[dev]"

test_commands:
  - python -m pytest tests/ -v

scoring_rubric:
  min_files: 3
  must_have_tests: true
  must_have_readme: false
  max_time_minutes: 30
  criteria:
    - "Core functionality works correctly"
    - "Tests cover edge cases"
    - "Clean code structure"
```

The challenge ID is derived from the file path: `easy/my-challenge`.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Human-readable challenge name |
| `language` | string | Primary programming language |
| `prompt` | string | Full prompt text given to the agent |
| `expected_files` | list | Files the agent should create |
| `test_commands` | list | Commands to run the test suite |
| `scoring_rubric` | object | Scoring criteria and constraints |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `time_limit_minutes` | int | 30 | Maximum wall-clock time |
| `setup_commands` | list | [] | Commands to run before testing |

## Adding Custom Agent Adapters

Implement the `AgentAdapter` abstract base class:

```python
# src/agentbench/adapters/my_agent.py

from pathlib import Path
from agentbench.adapters.base import AgentAdapter, AdapterResult

class MyAgentAdapter(AgentAdapter):
    @property
    def name(self) -> str:
        return "my-agent"

    def run_challenge(
        self,
        prompt: str,
        output_dir: Path,
        time_limit_minutes: int = 30,
    ) -> AdapterResult:
        # Invoke your agent here, write output to output_dir
        # ...
        return AdapterResult(
            time_taken_seconds=elapsed,
            prompts_used=num_prompts,
            success=True,
        )
```

Register it in the CLI adapter registry:

```python
from agentbench.cli import ADAPTERS
from agentbench.adapters.my_agent import MyAgentAdapter

ADAPTERS["my-agent"] = MyAgentAdapter
```

## Example Output

```
$ agentbench compare results/claude-code.json results/codex.json

┌─────────────────────┬─────────────────┬────────────┐
│ Agent               │ Aggregate Score │ Challenges │
├─────────────────────┼─────────────────┼────────────┤
│ claude-code         │            82.8 │          3 │
│ codex               │            74.2 │          3 │
└─────────────────────┴─────────────────┴────────────┘

┌──────────────────────┬─────────────┬───────┐
│ Challenge            │ claude-code │ codex │
├──────────────────────┼─────────────┼───────┤
│ easy/password-gen    │        91.4 │  78.1 │
│ easy/todo-api        │        84.9 │  70.0 │
│ easy/markdown-parser │        72.0 │  74.5 │
└──────────────────────┴─────────────┴───────┘
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Add challenges, adapters, or framework improvements
4. Ensure tests pass: `pytest tests/ -v --cov`
5. Submit a pull request with a clear description

### Development Setup

```bash
pip install -e ".[dev]"
pytest tests/ -v --cov --cov-report=term-missing
```

### Guidelines

- All data models must be immutable (frozen dataclasses)
- No mutable global state
- Functions under 50 lines, files under 800 lines
- Validate all inputs at boundaries
- Handle errors explicitly with clear messages

## License

MIT License. See [LICENSE](LICENSE) for details.
