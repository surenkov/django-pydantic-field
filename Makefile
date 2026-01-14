export DJANGO_SETTINGS_MODULE=tests.settings.django_test_settings

.PHONY: install
install:
	uv sync --group dev

.PHONY: build
build:
	uv build

.PHONY: migrations
migrations:
	uv run python3 -m django makemigrations --noinput

.PHONY: runserver
runserver:
	uv run python3 -m django migrate && \
	uv run python3 -m django runserver

.PHONY: check
check:
	uv run python3 -m django check

.PHONY: test
test: A=
test:
	uv run pytest $(A)

.PHONY: lint
lint: A=.
lint:
	uv run ty check $(A)

.PHONY: upload
upload:
	uv publish

.PHONY: upload-test
upload-test:
	uv publish --index testpypi

.PHONY: clean
clean:
	rm -rf dist/*
