.PHONY: test init ingest run export
init:
	python -m app.cli init-db
ingest:
	python -m app.cli ingest --pages 2
run:
	uvicorn app.main:app --reload
test:
	python -m unittest discover -s tests -v
export:
	python -m app.cli export --output cirp-eoi-monitor.xlsx
