VENV ?= .venv
PYTHON = $$(for python in $(VENV)/bin/python $(VENV)/bin/python3 $(VENV)/bin/python3.*; do \
	if [ -x "$$python" ]; then printf '%s' "$$python"; break; fi; \
done)
PIP := $(VENV)/bin/pip
CLI_STAMP := $(VENV)/.cli-installed
API_STAMP := $(VENV)/.api-installed
WEB_STAMP := web/node_modules/.installed

.PHONY: install install-cli install-api install-web backend frontend dev

$(VENV)/.created:
	python3 -m venv $(VENV)
	touch $(VENV)/.created

$(CLI_STAMP): requirements.txt $(VENV)/.created
	$(PIP) install -r requirements.txt
	touch $(CLI_STAMP)

$(API_STAMP): API/requirements.txt requirements.txt $(VENV)/.created
	$(PIP) install -r API/requirements.txt
	touch $(API_STAMP)

$(WEB_STAMP): web/package.json web/package-lock.json
	cd web && npm install
	touch $(WEB_STAMP)

install-cli: $(CLI_STAMP)

install-api: $(API_STAMP)

install-web: $(WEB_STAMP)

install: install-api install-web

backend: $(API_STAMP)
	$(PYTHON) -m uvicorn API.fastapi:app --host 0.0.0.0 --port 8000

frontend: $(WEB_STAMP)
	cd web && npm run dev

dev:
	$(MAKE) -j2 backend frontend
