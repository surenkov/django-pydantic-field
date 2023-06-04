
.PHONY: install
install:
	python3 -m pip install build twine
	python3 -m pip install -e .[dev,test]


.PHONY: build
build:
	python3 -m build


.PHONY: test
test: A=
test:
	pytest $(A)

.PHONY: lint
lint: A=.
lint:
	mypy $(A)


.PHONY: upload
upload:
	python3 -m twine upload dist/*


.PHONY: upload-test
upload-test:
	python3 -m twine upload --repository testpypi dist/*


.PHONY: clean
clean:
	rm -rf dist/*
