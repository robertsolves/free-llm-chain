# Work log

Newest first.

## 2026-11-03

**Load test: 60 of 60 requests answered**
- 30 `coder` requests (1.5k-token prompt, tools) in a row: Gemini 3.5 Flash served 6, then the chain moved on to
  3.6 Flash (1), 3 Flash (17) and OpenRouter dots.3 (6). Median 3.7s, slowest 33s (a timeout falling through).
- 30 `pipeline` requests: Groq gpt-oss-120b (3), Qwen 3.8 (8), gpt-oss-20b (13), then Z.ai GLM-4.5-Flash (6).
- Kilo, through `coder`: a small coding task (write `slugify.py` with tests) took 10 requests, with no rate limits;
  its 6 tests pass.

**Split out of reportaday; 9 more free pools**
- The chain lived in `reportaday/litellm/`. It now has its own repo so Kilo, OpenCode and any project can share it
  and `/update-chain` can keep it fresh. History before today: reportaday `docs/log.md` and `git log -- litellm`.
- Gemini quotas are per model, so each model is its own daily pool. Added 3.1 Pro preview, 3.6 Flash, 3 Flash preview,
  Gemini 4 Argon, 3.5 Flash-Lite and 3.1 Flash-Lite preview, on top of 3.5 Flash, 3.8 Flash and 3.1 Flash-Lite.
  OpenRouter adds North Mini Code and Nemotron 3.5 Super as fallbacks (one shared 50/day pool).
- Groups renamed after their model (`gemini-3.6-flash`, `openrouter-dots-3`); `coder` and `pipeline` kept.
- `scripts/scout.py` (report and probe) and `rejected.txt` (23 models that don't work on a free key, with reasons).
  The healthcheck reads the group names from `config.yaml`.
