.PHONY: setup update format lint test check clean build deploy

setup:
	poetry install

update:
	poetry update
	poetry export -f requirements.txt --output src/requirements.txt

format:
	poetry run ruff format

lint: format
	poetry run ruff check

test:
	poetry run pytest

# Non-mutating checks; mirrors CI
check:
	poetry run ruff format --check
	poetry run ruff check
	poetry run pytest
	poetry export -f requirements.txt | diff -q - src/requirements.txt

clean:
	rm -rf .aws-sam .pytest_cache .ruff_cache

build: lint test
	sam build

deploy: build
	sam deploy
