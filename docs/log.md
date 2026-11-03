# Work log

Newest first.

## 2026-11-03

**Split out of reportaday; 9 more free pools**
- The chain lived in `reportaday/litellm/`. It now has its own repo so Kilo, OpenCode and any project can share it
  and `/update-chain` can keep it fresh. History before today: reportaday `docs/log.md` and `git log -- litellm`.
- Gemini quotas are per model, so each model is its own daily pool. Added 3.1 Pro preview, 3.6 Flash, 3 Flash preview,
  Gemini 4 Argon, 3.5 Flash-Lite and 3.1 Flash-Lite preview, on top of 3.5 Flash, 3.8 Flash and 3.1 Flash-Lite.
  OpenRouter adds North Mini Code and Nemotron 3.5 Super as fallbacks (one shared 50/day pool).
- Groups renamed after their model (`gemini-3.6-flash`, `openrouter-dots-3`); `coder` and `pipeline` kept.
- `scripts/scout.py` (report and probe) and `rejected.txt` (23 models that don't work on a free key, with reasons).
  The healthcheck reads the group names from `config.yaml`.
