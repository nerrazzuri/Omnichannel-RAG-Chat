PYTHON := python3
PIP := pip3

.PHONY: help setup-dev lint typecheck test security node-lint node-format backend-up backend-down audit-rag audit-load pre-commit-install

help:
	@echo "Targets:"
	@echo "  setup-dev         Install Python dev deps"
	@echo "  lint              Run black, flake8"
	@echo "  typecheck         Run mypy on backend and devops"
	@echo "  test              Run backend pytest"
	@echo "  security          Run bandit and detect-secrets"
	@echo "  node-lint         Run eslint on frontend and gateway"
	@echo "  node-format       Run prettier --check on frontend and gateway"
	@echo "  backend-up        docker compose up (detached)"
	@echo "  backend-down      docker compose down"
	@echo "  audit-rag         Run RAG evaluator script"
	@echo "  audit-load        Run Locust headless smoke"
	@echo "  pre-commit-install Install pre-commit hooks"

setup-dev:
	$(PIP) install -r backend/requirements.txt -r requirements-dev.txt

lint:
	black --check backend devops || (echo "Run black to format" && exit 1)
	flake8 backend devops

typecheck:
	mypy backend devops

test:
	pytest -q backend/tests

security:
	bandit -r backend -x backend/tests
	detect-secrets scan --all-files --json > devops/reports/detect-secrets.json || true
	$(PYTHON) - <<'PY'
import json,sys
data=json.load(open('devops/reports/detect-secrets.json'))
results=data.get('results') or {}
if results:
    print('Potential secrets found by detect-secrets: devops/reports/detect-secrets.json')
    sys.exit(1)
print('No potential secrets detected')
PY

node-lint:
	cd gateway && npm ci && npx eslint . --ext .ts,.tsx,.js
	cd frontend && npm ci && npx eslint . --ext .ts,.tsx,.js

node-format:
	cd gateway && npx prettier -c .
	cd frontend && npx prettier -c .

backend-up:
	docker compose up -d

backend-down:
	docker compose down -v || true

audit-rag:
	AI_CORE_URL?=http://localhost:8000
	$(PYTHON) devops/audits/rag_eval.py --base $${AI_CORE_URL}

audit-load:
	AI_CORE_URL?=http://localhost:8000
	locust -f devops/audits/locustfile.py --host $${AI_CORE_URL} --headless -u 50 -r 10 -t 1m

pre-commit-install:
	pre-commit install --install-hooks

