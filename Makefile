.PHONY: bootstrap lint typecheck test check

UV ?= uv
PYTEST_ARGS ?=

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

test:
	$(UV) run pytest $(PYTEST_ARGS)

check: lint test
