# Progress Tracker

A personal application for tracking tennis practice, gym workouts, and
body measurements, built alongside a DevOps workflow for testing,
containerization, infrastructure, and deployment.

**Status: In development.**

## Features

- **Tennis:** session logging, match scores, training goals, and progress tracking.
- **Gym:** reusable workout templates, a shared exercise library,
  set and duration logging, goals, and performance history.
- **Measurements:** bodyweight, optional waist measurements, and weekly trends.

Records belong to the signed-in user. The interface is mobile-friendly.

## Stack

**Application:** Python, Django, PostgreSQL  
**Delivery:** Docker Compose, Gunicorn, WhiteNoise, GitHub Actions  
**Infrastructure:** Terraform, AWS EC2, ECR, S3, and Systems Manager

## DevOps Workflow

- Automated application tests and migration checks.
- Container verification, including database outage and recovery.
- Encrypted database backups with automated restore testing.
- Container image publishing to ECR.
- Manually triggered deployment through Systems Manager using GitHub OIDC.
- Separate Terraform configurations for state storage, shared services,
  and runtime infrastructure.

AWS runtime resources are created for testing and destroyed afterward
to control costs. There is no permanent public demo.

## Quick Start

Requires Docker, Docker Compose, and VS Code with the Dev Containers
extension. On Windows, use WSL2.

```bash
git clone https://github.com/ori2370/progress-tracker.git
cd progress-tracker
cp .env.example .env
```

Replace the secret-key and database-password placeholders in `.env` with
generated values. Do not commit `.env`.

Open the project in VS Code and select **Dev Containers: Reopen in Container**.

In the Dev Container terminal:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

Open `http://localhost:8000/admin/login/` to sign in, then visit
`/tennis/` or `/gym/`.

## Tests

Run in the Dev Container:

```bash
python manage.py test tracking
```

## Project Status

Tennis, Gym, measurement tracking, and duration logging are implemented.

Next priorities include an exercise catalog, home-server deployment,
scheduled off-host backups, monitoring, and rollback procedures.

Posture programs and private photo uploads are planned. Backup encryption
is implemented; application-level field and photo encryption are not.

This is a learning and personal-use project, not a production-ready service.

## Documentation

- [Database backup and restore](deployment/BACKUPS.md)

## Development Approach

Developed with assistance from ChatGPT for implementation guidance,
debugging, and documentation. Changes are tested locally and through
GitHub Actions.