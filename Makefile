PYTHON ?= python3
NIX ?= nix

.DEFAULT_GOAL := run
.PHONY: run test check nixos-check nixos-image clean help

run:
	$(PYTHON) main.py

test:
	$(PYTHON) -m unittest discover -s tests -v

check:
	$(PYTHON) -m compileall -q main.py recorder tests

nixos-check:
	$(NIX) flake check --no-build "path:$(CURDIR)"

nixos-image:
	$(NIX) build "path:$(CURDIR)#sd-image"

clean:
	find recorder tests -type d -name __pycache__ -prune -exec rm -rf -- {} +
	rm -rf -- __pycache__

help:
	@printf '%s\n' \
	  'make run    Start recording (also the default for make)' \
	  'make test   Run all tests' \
	  'make check  Check Python syntax' \
	  'make nixos-check  Evaluate the NixOS configuration' \
	  'make nixos-image  Build the Pi 4 SD image (requires an AArch64 builder)' \
	  'make clean  Remove generated Python caches' \
	  'make help   Show these commands' \
	  '' \
	  'Override the interpreter with PYTHON, e.g. make test PYTHON=.venv/bin/python'
