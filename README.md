# SQR Safe and Sound Project

A small laundry monitoring web application for tracking washing machines and dryers in dorm buildings.

## Overview

This project helps users check machine availability, submit new status reports, and view recent report history.

The system consists of:
- a **Streamlit** frontend,
- a **FastAPI** backend,
- a database layer built with **SQLAlchemy**,
- optional **Yandex Maps** integration for address display.

## Main features

- View machines by building and floor
- See current machine status
- Submit a report for a machine
- Add remaining time for busy machines
- View report history for a selected machine
- Display a selected address on Yandex Maps

## Status logic

A machine report can have one of these statuses:
- `free`
- `busy`
- `unavailable`

If a machine is reported as `busy` with a remaining time, the system keeps it busy until that time expires.

If a machine is reported as `busy` without a remaining time, the system later marks it as `probably_free`.

## Tech stack

- Python 3.12+
- Streamlit
- FastAPI
- SQLAlchemy
- Poetry
- Pytest
- Hypothesis
- Flake8
- Radon
- Bandit
- Locust

## Project structure

```text
SQR-Safe-And-Sound-Project/
├── .github/workflows/      # CI pipeline
├── src/                    # backend logic, database layer, external API helpers
├── tests/                  # automated tests
├── .env_example            # example environment variables
├── pyproject.toml          # dependencies and project config
├── poetry.lock
├── README.md
└── streamlit_app.py        # frontend application
````

## Running locally

### 1. Install dependencies

```bash
poetry install --no-root
```

### 2. Configure environment variables

You can create a local `.env` file based on `.env_example`.
```env
DATABASE_URL="sqlite:///laundry.db"
YANDEX_MAPS_API_KEY=your_key_here
```

> Note: SQLite is used by default if `DATABASE_URL` is not set.

### 3. Run the backend

```bash
poetry run uvicorn src.api:app --reload
```

### 4. Run the frontend

```bash
poetry run streamlit run streamlit_app.py
```

## API endpoints

Main API endpoints:

* `GET /machines`
* `POST /report`
* `GET /machines/{machine_id}/history`

## Seed data

On first run, the database is automatically initialized and filled with machine data.

Current setup:

* buildings **1–5** have **4 floors**
* buildings **6–7** have **13 floors**
* each floor contains **2 washers** and **2 dryers**

## Quality Gate / CI

The repository includes an automated CI pipeline with checks for:

* dependency validation
* cyclomatic complexity
* maintainability index
* style (PEP8)
* tests
* coverage
* security scan
* performance smoke test

## Note
This project was created as part of the SQRS course in Innopolis university for BS23

