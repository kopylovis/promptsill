PYTHON ?= python3

.PHONY: test

test:
	@$(PYTHON) -m unittest discover -s tests
	@echo '{}' | $(PYTHON) ./promptsill >/dev/null
	@echo '{"workspace":{"current_dir":"/tmp"},"context_window":{"used_percentage":5}}' | COLUMNS=20 LC_ALL=en_US.UTF-8 $(PYTHON) ./promptsill | grep -q context
	@$(PYTHON) ./promptsill preview --width 200 >/dev/null
