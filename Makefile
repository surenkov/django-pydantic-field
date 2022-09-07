
.PHONY: install
install:
	python3 -m venv .env
	. .env/bin/activate
	python3 -m pip install build twine
	python3 -m pip install -e .[dev,rest]


.PHONY: activate
activate:
	@ . .env/bin/activate


.PHONY: build
build: activate
build:
	python3 -m build


.PHONY: test
test: A=
test: activate
test:
	pytest $(A)

.PHONY: lint
lint: A=.
lint: activate
lint:
	mypy $(A)


.PHONY: upload
upload: activate
upload:
	python3 -m twine upload dist/*


.PHONY: upload-test
upload-test: activate
upload-test:
	python3 -m twine upload --repository testpypi dist/*


.PHONY: clean
clean:
	rm -rf dist/*
