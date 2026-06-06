PYTHON := .venv/bin/python

.PHONY: help server connector webapp painter logviewer services

help:
	@printf "Targets:\n"
	@printf "  make server     # run backbone server on :8000\n"
	@printf "  make connector  # run ESP serial connector on :8001\n"
	@printf "  make webapp     # run read-only viewer on :8002\n"
	@printf "  make painter    # run manual paint app on :8003\n"
	@printf "  make logviewer  # run log viewer on :8004\n"
	@printf "  make services   # generate systemd service files\n"

server:
	$(PYTHON) -m uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload

connector:
	$(PYTHON) -m uvicorn connector.main:app --host 0.0.0.0 --port 8001 --reload

webapp:
	$(PYTHON) -m uvicorn webapp.main:app --host 0.0.0.0 --port 8002 --reload

painter:
	$(PYTHON) -m uvicorn painter.main:app --host 0.0.0.0 --port 8003 --reload

logviewer:
	$(PYTHON) -m uvicorn logviewer.main:app --host 0.0.0.0 --port 8004 --reload

services:
	./setup_services.sh
