PYTHON := python3.12
VENV_DIR := $(PWD)/.venv
VENV_PYTHON := $(VENV_DIR)/bin/python

setup-env:
	$(PYTHON) -m venv .venv
	. .venv/bin/activate
	$(VENV_PYTHON) -m pip install --upgrade pip setuptools wheel
	$(VENV_PYTHON) -m pip install virtualenv

install-env:
	$(VENV_PYTHON) -m pip install -r requirements.txt
# 	$(VENV_PYTHON) -m pip install -r tests/requirements-linter.txt

db-init:
	psql -h database_us-east-1.diallink.dev -U postgres -c "CREATE USER transcription_dev WITH PASSWORD 'KsCMxF669GyX';" || true
	psql -h database_us-east-1.diallink.dev -U postgres -c "CREATE DATABASE transcription_dev OWNER transcription_dev;" || true
	psql -h database_us-east-1.diallink.dev -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE transcription_dev TO transcription_dev;" || true

start:
	cd app && $(VENV_PYTHON) -m uvicorn app:app --host 0.0.0.0 --port 9001

start-dev:
	cd app && $(VENV_PYTHON) -m uvicorn app:app --host 0.0.0.0 --port 9001 --reload

test:
	$(VENV_PYTHON) -m pytest tests/ -v

##
# Formatter
##
format-imports:
	isort --atomic --skip .venv --skip venv .

format-code:
	black --exclude="(.venv|venv)" .

format: format-imports format-code
	# Imports sorted, code formatted

##
# Linter
##
lint:
	# Run Linters
	# - isort: Check if imports are correctly sorted/formatted
	isort --check  --skip .venv --skip venv .
	# - Black: Check if code is correctly formatted
	black --check  --exclude="(.venv|venv)" .
	# - Check the Code with ruff
	ruff check --exclude .venv --exclude venv .

lint-fix:
	ruff check --fix --exclude .venv --exclude venv .