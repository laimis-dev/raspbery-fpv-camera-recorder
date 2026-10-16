PYTHON ?= python3

.DEFAULT_GOAL := run
.PHONY: run test check clean help

run:
	$(PYTHON) main.py

test:
	$(PYTHON) -m unittest discover -s tests -v

check:
	$(PYTHON) -m compileall -q main.py recorder tests

clean:
	find recorder tests -type d -name __pycache__ -prune -exec rm -rf -- {} +
	rm -rf -- __pycache__

help:
	@printf '%s\n' \
	  'make run    Start recording (also the default for make)' \
	  'make test   Run all tests' \
	  'make check  Check Python syntax' \
	  'make clean  Remove generated Python caches' \
	  'make help   Show these commands' \
	  '' \
	  'Override the interpreter with PYTHON, e.g. make test PYTHON=.venv/bin/python'
