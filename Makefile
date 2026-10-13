.PHONY: setup dev dev-api dev-voice dev-web test test-api test-voice test-web check-voice lint seed gen-api deploy deploy-api deploy-voice deploy-web

setup:
	cd api && pip install -e ".[dev]"
	cd voice && pip install -e ".[dev]"
	cd web && npm install

dev:
	$(MAKE) -j3 dev-api dev-voice dev-web

dev-api:
	cd api && uvicorn app.main:app --reload --port 8000
dev-voice:
	cd voice && uvicorn app.main:app --reload --port 8001
dev-web:
	cd web && npm run dev

test: test-api test-voice test-web

# tdd-marked tests fail by design until implemented; run them with: cd api && pytest -m tdd
test-api:
	cd api && ruff check . && pytest -m "not tdd"
test-voice: check-voice
	cd voice && ruff check . && pytest
test-web:
	cd web && npm run lint && npm test

check-voice:
	python scripts/check_no_db_in_voice.py

lint: check-voice
	cd api && ruff check .
	cd voice && ruff check .
	cd web && npm run lint

seed:
	python seed/seed.py

gen-api:
	cd api && python -m scripts.export_openapi ../web/openapi.json
	cd web && npm run gen:api

deploy: deploy-api deploy-voice deploy-web
deploy-api:
	./deploy/deploy-api.sh
deploy-voice:
	./deploy/deploy-voice.sh
deploy-web:
	./deploy/deploy-web.sh
