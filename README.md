# free-llm-chain

One OpenAI-compatible endpoint (`http://127.0.0.1:4000/v1`) in front of every free LLM tier that works: Gemini,
OpenRouter `:free`, Groq, Z.ai and Cloudflare Workers AI. When one model's free quota runs out, LiteLLM moves to the
next, so a coding agent keeps going.

```sh
cp .env.example .env        # fill in the keys
docker compose up -d
bash scripts/healthcheck.sh
```

Point a client at it with base URL `http://127.0.0.1:4000/v1`, the `LITELLM_MASTER_KEY` as the API key, and model
`coder` (coding agents, tool calls, big prompts) or `pipeline` (small JSON prompts).

Keep it fresh with `/update-chain` in Claude Code (or ask any agent to follow `.agents/commands/update-chain.md`):
it drops retired models, probes new free ones, restarts and commits. `python3 scripts/scout.py` alone prints what
changed.
