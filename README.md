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

There are two ways to run a workflow:

1. Directly run the workflow with Python, based on the `__main__` block:

```bash
python workflows/example.py
```

2. Deploy the workflow as a Prefect deployment, and run it:

```bash
prefect deployment build workflows/example.py:main --name example --cron "0 8 * * *"
prefect deployment run example
```

> ![NOTE]
> The `cron` parameter is used to schedule the deployment.
> You need to set the entrypoint to the `main` function of the workflow using the `@flow` decorator, and the function name in the path to the workflow file e.g. `workflows/example.py:main` or `workflows/github.py:backup_github_repositories`

## Registering Integration Blocks:

### GitHub

```bash
prefect block register -m prefect_github
```

Go to http://localhost:4200 in your browser to see the project.