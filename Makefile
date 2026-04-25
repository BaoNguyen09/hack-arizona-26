PYTHON ?= python

.PHONY: install api test lint format frontend

install:
	$(PYTHON) -m pip install -r requirements.txt

api:
	uvicorn backend.app.main:app --reload

test:
	pytest backend/tests

lint:
	ruff check backend scripts

format:
	ruff format backend scripts

frontend:
	cd frontend && npm run dev
