# ARIA Makefile
# Common tasks for development and operations

.SHELL := /usr/bin/env bash

.ONESHELL:

# Default target
.DEFAULT_GOAL := help

# ARIA home
ARIA_HOME := /home/fulvio/coding/aria
VENV := $(ARIA_HOME)/.venv

# Python interpreter
PYTHON := $(VENV)/bin/python

# Help
.PHONY: help
help:
	@echo "ARIA Makefile"
	@echo "================"
	@echo ""
	@echo "Development:"
	@echo "  make install        - Install dependencies (uv sync)"
	@echo "  make dev-install   - Install dev dependencies"
	@echo "  make lint          - Run ruff linter"
	@echo "  make format        - Format code with ruff"
	@echo "  make typecheck      - Run mypy type checker"
	@echo "  make test          - Run test suite"
	@echo "  make test-unit     - Run unit tests only"
	@echo "  make quality        - Run all quality gates"
	@echo ""
	@echo "Operations:"
	@echo "  make bootstrap      - Run bootstrap script"
	@echo "  make backup        - Create backup"
	@echo "  make db-smoke      - Run database smoke tests"
	@echo "  make systemd-start - Start systemd services"
	@echo "  make systemd-stop  - Stop systemd services"
	@echo "  make systemd-status - Show service status"
	@echo ""

# === Development tasks ===

.PHONY: install
install:
	uv sync

.PHONY: dev-install
dev-install:
	uv sync --dev

.PHONY: lint
lint:
	ruff check $(ARIA_HOME)/src

.PHONY: format
format:
	ruff format $(ARIA_HOME)/src

.PHONY: typecheck
typecheck:
	mypy $(ARIA_HOME)/src

.PHONY: test
test:
	pytest -q

.PHONY: test-unit
test-unit:
	pytest -q tests/unit

.PHONY: test-integration
test-integration:
	pytest -q tests/integration

.PHONY: quality
quality: lint format typecheck test

# === Operations ===

.PHONY: bootstrap
bootstrap:
	$(ARIA_HOME)/scripts/bootstrap.sh

.PHONY: bootstrap-check
bootstrap-check:
	$(ARIA_HOME)/scripts/bootstrap.sh --check

.PHONY: backup
backup:
	$(ARIA_HOME)/scripts/backup.sh

.PHONY: db-smoke
db-smoke:
	$(ARIA_HOME)/scripts/smoke_db.sh

.PHONY: systemd-install
systemd-install:
	$(ARIA_HOME)/scripts/install_systemd.sh install

.PHONY: systemd-start
systemd-start:
	$(ARIA_HOME)/scripts/install_systemd.sh start

.PHONY: systemd-stop
systemd-stop:
	$(ARIA_HOME)/scripts/install_systemd.sh stop

.PHONY: systemd-status
systemd-status:
	$(ARIA_HOME)/scripts/install_systemd.sh status

.PHONY: systemd-enable
systemd-enable:
	$(ARIA_HOME)/scripts/install_systemd.sh enable

.PHONY: systemd-disable
systemd-disable:
	$(ARIA_HOME)/scripts/install_systemd.sh disable

# === Cleanup ===

.PHONY: clean
clean:
	rm -rf $(ARIA_HOME)/.venv
	rm -f $(ARIA_HOME)/uv.lock

.PHONY: clean-logs
clean-logs:
	find $(ARIA_HOME)/.aria -name "*.log" -delete
	find $(ARIA_HOME)/.aria -name "logs" -type d -exec rm -rf {} + 2>/dev/null || true

.PHONY: clean-all
clean-all: clean clean-logs
	rm -f $(ARIA_HOME)/.aria/runtime/*.db
