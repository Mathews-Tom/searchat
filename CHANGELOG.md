# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

## 0.2.2
- Fix: add `eval_type_backport` for Python 3.9 so Pydantic/FastAPI can evaluate modern type syntax.

## 0.2.1
- Fix: make package importable on Python 3.9 by deferring annotation evaluation.

## 0.2.0
- Packaging: migrate build backend to hatchling; ship web assets + config templates.
- Connectors: add Codex and Gemini CLI connectors; enable entry-point discovery.
- CI: add build + install smoke tests.
- Web: `searchat-web` opens the default browser automatically on start.
