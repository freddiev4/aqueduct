# aqueduct
A repository for DAG-based backup to NAS

## Prerequisites

Ensure [`uv`](https://docs.astral.sh/uv/) is installed following their [official documentation](https://docs.astral.sh/uv/getting-started/installation/).

## Setup Steps

1. Activate the virtual environment:
   ```bash
   source .venv/bin/activate
   ```

2. Install dependencies:

```bash
uv pip install -e .
```



## Running Prefect

Start the Prefect UI & server using docker:

```bash
docker run -p 4200:4200 --rm prefecthq/prefect:3-latest -- prefect server start --host 0.0.0.0
```

## Running the example workflow

```bash
prefect deployment build workflows/example.py:main --name example --cron "0 8 * * *"
prefect deployment run example
```

## Registering Integration Blocks:

### GitHub

```bash
prefect block register -m prefect_github
```

Go to http://localhost:4200 in your browser to see the project.