ART := artifacts/2026-10-23-recon

.PHONY: test demo eval bench gate all

test:
	uv run pytest

demo:
	PYTHONPATH=$(ART) uv run python -m recon.cli demo

eval:
	PYTHONPATH=$(ART) uv run python -m recon.cli eval

bench:
	PYTHONPATH=$(ART) uv run python -m recon.cli bench

gate:
	uv run python tools/gate.py $(ART)

all: test eval bench gate
