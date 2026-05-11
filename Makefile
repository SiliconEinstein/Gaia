.PHONY: bootstrap lint typecheck test check

UV ?= uv
PYTEST_ARGS ?=

bootstrap:
	$(UV) sync --extra dev
	$(UV) run pre-commit install

lint:
	$(UV) run pre-commit run --all-files

typecheck:
	$(UV) run mypy

test:
	$(UV) run pytest $(PYTEST_ARGS)

check: lint test
