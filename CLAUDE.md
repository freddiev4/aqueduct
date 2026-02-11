# CLAUDE.md

Aqueduct is a DAG-based backup system for archiving personal data from various platforms (GitHub, Twitter/X, Instagram, Notion) to local storage. It uses Prefect for workflow orchestration.

## Rules

- All imports must be at the top of a given file. Do not import libraries inside of functions, classes, etc.
- Use `uv` for Python version management and dependency installation.
- When changes are made to `infra/bootstrap-server.sh`, always update `infra/README.md`.

## Creating New Workflows

When creating a new workflow, first research the available APIs and ensure:

1. The APIs are not deprecated. (e.g., Google Photos API was deprecated — see `docs/google-photos/`)
2. The workflows can be automated. If manual auth is required, the workflow goes in `workflows/cannot-automate/`.

Use the [workflow-builder](.claude/agents/workflow-builder.md) subagent, then the idempotency agent, then the workflow-testing-agent.

## Documentation

Documentation for new features should go in `docs/<feature>/` (no date prefix). See [docs/](#docs-map) below for existing documentation.

## Quick Reference

```bash
source .venv/bin/activate          # Activate venv
uv pip install -e .                # Install dependencies
python workflows/<platform>.py     # Run a workflow
```

Amazon workflow requires Python 3.12 or 3.11 (`uv venv --python 3.12`).

## Docs Map

**Development & Architecture:**
- [Development Guide](docs/development.md) — setup, running workflows, creating new ones
- [Architecture](docs/architecture.md) — workflow structure, patterns, file listing

**Credentials & Setup:**
- [Credentials Setup](docs/CREDENTIALS_SETUP.md) — unified guide for all workflow credentials

**Per-Workflow Docs:**
- [Google Drive](docs/google-drive/) — setup, implementation, test reports
- [Reddit](docs/reddit/) — setup, plan, implementation docs
- [Amazon](docs/amazon/) — setup guide
- [Google Photos](docs/google-photos/) — setup (API deprecated, cannot automate)
- [LinkedIn](docs/linkedin/) — research, plan, implementation docs
- [Local K8s](docs/local-k8s/) — local Kubernetes deployment docs

**Infrastructure:**
- [Infrastructure Setup](infra/README.md) — bootstrap server script
- [Kubernetes](infra/k8s/README.md) — local K8s deployment

**Other:**
- [Workflows README](workflows/README.md) — workflow overview
- [Cannot Automate](workflows/cannot-automate/README.md) — workflows that require manual intervention
- [Workflow Automation Status](docs/WORKFLOW_AUTOMATION_STATUS.md) — automation readiness per workflow
- [Workflow Fixes Summary](docs/WORKFLOW_FIXES_SUMMARY.md) — historical fix log
