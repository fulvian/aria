# Contributing to ARIA

Welcome! This document outlines the development practices and conventions for ARIA.

## Development Philosophy

ARIA follows the **Ten Commandments** from the Foundation Blueprint (§16):

1. **Isolation First**: Always work within the isolated ARIA workspace
2. **Upstream Invariance**: Never modify KiloCode source directly
3. **Polyglot Pragmatism**: KiloCode = TypeScript, ARIA layer = Python, MCP = glue
4. **Local-First, Privacy-First**: No secrets in plaintext, data stays local
5. **Actor-Aware Memory**: Tag all data with its source actor
6. **Verbatim Preservation**: Raw Tier 0 is authoritative; syntheses are derived
7. **HITL on Destructive Actions**: Destructive/costly actions require human approval
8. **Tool Priority Ladder**: MCP > Skill > Python script
9. **Scoped Toolsets ≤ 20**: No sub-agent gets more than 20 tools
10. **Self-Documenting Evolution**: Divergences must be registered via ADR

## Getting Started

### Prerequisites

- Python >= 3.11
- `uv` package manager
- Node.js (for KiloCode CLI)
- `sops`, `age`, `sqlite3`

### Bootstrap

```bash
# Install all dependencies (Python + Node)
./scripts/bootstrap.sh

# Verify installation
./bin/aria --help
```

### Development Setup

```bash
# Install Python dependencies in dev mode
uv sync --dev

# Run tests
pytest -q

# Lint and type-check
ruff check .
ruff format --check .
mypy src
```

## Code Standards

### Python

- **Formatter**: `ruff format`
- **Linter**: `ruff check`
- **Type checking**: `mypy src`
- **Imports**: Groups in order (stdlib, third-party, local); absolute imports from `aria`
- **Naming**: snake_case (modules/functions/variables), PascalCase (classes), UPPER_SNAKE_CASE (constants)
- **Types**: Concrete types preferred; `Any` tightly scoped

### Git Workflow

- **Branch naming**: `feature/<description>`, `fix/<description>`, `sprint-00/<work-package>`
- **Commits**: Conventional Commits format (`feat:`, `fix:`, `docs:`, etc.)
- **PR size**: < 400 lines changed preferred
- **Never force-push to main**

See [AGENTS.md](./AGENTS.md) for full agent rules.

## Secrets Management

Secrets are encrypted with SOPS + age:

```bash
# Edit encrypted secrets
sops .aria/credentials/secrets/api-keys.enc.yaml

# Never commit plaintext secrets
```

Age keys are stored in `~/.config/sops/age/keys.txt` (outside the repository).

## Adding New Components

### New Python Module

1. Add to `src/aria/<module>/`
2. Export public API in `__init__.py`
3. Add type hints for all public functions
4. Write unit tests in `tests/unit/`
5. Update schema if database-related

### New Agent Definition

1. Create markdown file in `.aria/kilocode/agents/<agent-name>.md`
2. Follow the frontmatter format in §8 of the Blueprint
3. Register in the appropriate sub-agent category

### New Skill

1. Create directory `.aria/kilocode/skills/<skill-slug>/`
2. Write `SKILL.md` following §9.1 format
3. Add to `_registry.json`

## ADR Process

Architecture Decision Records go in `docs/foundation/decisions/ADR-NNNN-<slug>.md`.

Template:
- Status (Proposed | Accepted | Rejected | Superseded)
- Context, Decision, Consequences, Alternatives, References

## Reporting Issues

For technical issues or feature requests, open an issue with:
- Clear description
- Blueprint section reference (if applicable)
- Reproduction steps (for bugs)

## Questions?

Refer to the [Foundation Blueprint](./docs/foundation/aria_foundation_blueprint.md) first. For clarifications, open a discussion.
