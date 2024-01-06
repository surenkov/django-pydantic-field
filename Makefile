.PHONY: install build test lint upload upload-test clean

install:
	python3 -m pip install build twine
	python3 -m pip install -e .[dev,test]

build:
	python3 -m build

migrations:
	DJANGO_SETTINGS_MODULE="tests.settings.django_test_settings" python3 -m django makemigrations --noinput

test: A=
test:
	pytest $(A)

lint: A=.
lint:
	mypy $(A)

upload:
	python3 -m twine upload dist/*

upload-test:
	python3 -m twine upload --repository testpypi dist/*

clean:
	rm -rf dist/*
