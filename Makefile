PYTHON ?= python3
NIX ?= nix
DOCKER ?= docker
ZSTD ?= zstd

.DEFAULT_GOAL := run
.PHONY: run test check image image-check nixos-check nixos-image clean help

run:
	$(PYTHON) main.py

test:
	$(PYTHON) -m unittest discover -s tests -v

check:
	$(PYTHON) -m compileall -q main.py recorder scripts tests
	sh -n scripts/build_pi_image.sh

image:
	DOCKER="$(DOCKER)" ZSTD="$(ZSTD)" PYTHON="$(PYTHON)" sh scripts/build_pi_image.sh

image-check:
	$(PYTHON) scripts/validate_pi_image.py

nixos-check:
	$(NIX) flake check --no-build "path:$(CURDIR)"

nixos-image:
	$(NIX) build "path:$(CURDIR)#sd-image"

clean:
	find recorder scripts tests -type d -name __pycache__ -prune -exec rm -rf -- {} +
	rm -rf -- __pycache__

help:
	@printf '%s\n' \
	  'make run    Start recording and the browser page (also the default for make)' \
	  'make test   Run all tests' \
	  'make check  Check Python and image-builder shell syntax' \
	  'make image  Build and decompress the Pi 4 image (requires Docker, Python 3, and zstd)' \
	  'make image-check  Validate the exported Pi image layout without accessing devices' \
	  'make nixos-check  Evaluate the NixOS configuration' \
	  'make nixos-image  Build the Pi 4 SD image (requires an AArch64 builder)' \
	  'make clean  Remove generated Python caches' \
	  'make help   Show these commands' \
	  '' \
	  'Override the interpreter with PYTHON, e.g. make test PYTHON=.venv/bin/python'
