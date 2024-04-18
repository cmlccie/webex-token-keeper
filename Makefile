.PHONY: setup format lint clean build deploy

setup:
	poetry install

update:
	poetry update
	poetry export -f requirements.txt --output src/requirements.txt

format:
	poetry run ruff format

lint: format
	poetry run ruff check

build: lint
	sam build

deploy: build
	sam deploy
