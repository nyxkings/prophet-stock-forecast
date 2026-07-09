.PHONY: install install-dev lint format type-check test clean run dashboard backtest analyze risk sector score-outcomes evaluate

install:
	poetry install --no-dev

install-dev:
	poetry install

lint:
	poetry run ruff check src tests
	poetry run black --check src tests

format:
	poetry run ruff check --fix src tests
	poetry run black src tests

type-check:
	poetry run mypy src

test:
	poetry run pytest

clean:
	find . -type d -name "__pycache__" -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -r {} +
	find . -type d -name ".pytest_cache" -exec rm -r {} +
	find . -type d -name ".mypy_cache" -exec rm -r {} +
	find . -type d -name ".ruff_cache" -exec rm -r {} +
	find . -type d -name "htmlcov" -exec rm -r {} +

check: format lint type-check test

run:
	poetry run python -m src.main

dashboard:
	poetry run streamlit run dashboard.py

backtest:
	poetry run python -m src.main backtest

analyze:
	poetry run python -m src.main analyze

risk:
	poetry run python -m src.main risk

sector:
	poetry run python -m src.main sector

score-outcomes:
	poetry run python -m src.main score-outcomes

evaluate:
	poetry run python -m src.main evaluate --mode smoke

