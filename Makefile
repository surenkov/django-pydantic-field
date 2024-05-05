export DJANGO_SETTINGS_MODULE=tests.settings.django_test_settings

.PHONY: install
install:
	python3 -m pip install build twine
	python3 -m pip install -e .[dev,test]

.PHONY: build
build:
	python3 -m build

.PHONY: migrations
migrations:
	python3 -m django makemigrations --noinput

.PHONY: runserver
runserver:
	python3 -m django migrate && \
	python3 -m django runserver

.PHONY: check
check:
	python3 -m django check

.PHONY: test
test: A=
test:
	pytest $(A)

.PHONY: lint
lint: A=.
lint:
	python3 -m mypy $(A)

.PHONY: upload
upload:
	python3 -m twine upload dist/*

.PHONY: upload-test
upload-test:
	python3 -m twine upload --repository testpypi dist/*

.PHONY: clean
clean:
	rm -rf dist/*
