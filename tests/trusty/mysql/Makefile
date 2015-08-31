#!/usr/bin/make
PYTHON := /usr/bin/env python
export PYTHONPATH := hooks

virtualenv:
	virtualenv .venv
	.venv/bin/pip install flake8 nose mock six

lint: virtualenv
	.venv/bin/flake8 --exclude hooks/charmhelpers hooks
	@charm proof

test: virtualenv
	@echo Starting tests...
	@sudo apt-get install python-six
	@.venv/bin/nosetests --nologcapture unit_tests

bin/charm_helpers_sync.py:
	@mkdir -p bin
	@bzr cat lp:charm-helpers/tools/charm_helpers_sync/charm_helpers_sync.py \
        > bin/charm_helpers_sync.py

sync: bin/charm_helpers_sync.py
	$(PYTHON) bin/charm_helpers_sync.py -c charm-helpers.yaml
