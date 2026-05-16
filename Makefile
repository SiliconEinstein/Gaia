.PHONY: bootstrap lint typecheck test test-fast test-slow test-all docs-build docs-serve check

UV ?= uv
PYTEST_ARGS ?=
PYTEST_FAST_MARK ?= not slow
PYTEST_SLOW_MARK ?= slow

bootstrap:
	$(UV) sync --extra dev
	git config extensions.worktreeConfig true
	-git config --worktree --unset core.hooksPath
	mkdir -p .githooks
	$(UV) run pre-commit install --hook-type pre-commit --hook-type pre-push --hook-type commit-msg
	@hooks_src="$$(git rev-parse --git-path hooks)"; \
		for h in pre-commit pre-push commit-msg; do \
			if [ -f "$$hooks_src/$$h" ]; then mv -f "$$hooks_src/$$h" ".githooks/$$h"; fi; \
		done
	git config --worktree core.hooksPath .githooks

lint:
	$(UV) run pre-commit run --all-files

typecheck:
	$(UV) run mypy

test: test-fast

test-fast:
	$(UV) run pytest -n auto --no-cov -m "$(PYTEST_FAST_MARK)" $(PYTEST_ARGS)

test-slow:
	$(UV) run pytest -n auto --no-cov -m "$(PYTEST_SLOW_MARK)" $(PYTEST_ARGS)

test-all:
	$(UV) run pytest -n auto $(PYTEST_ARGS)

docs-build:
	$(UV) run --extra docs mkdocs build --strict

docs-serve:
	$(UV) run --extra docs mkdocs serve

check: lint test-all
