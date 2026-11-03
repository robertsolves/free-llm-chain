# free-llm-chain: notes for agents

A LiteLLM proxy on `127.0.0.1:4000` that chains every free LLM tier we can find, so coding agents (Kilo,
OpenCode) and small-prompt pipelines (reportaday) get as much free capacity as possible.

- `config.yaml`: the models and the two fallback lanes, `coder` and `pipeline`. The pool notes at its top decide
  where a model goes.
- `rejected.txt`: models tried and dropped, with dates. The scout hides them.
- `hooks.py`: normalises message content so every free provider accepts it.
- `scripts/scout.py`: what changed at the providers (gone models, new candidates, quotas, recent 429s); `probe <model>`
  tests one model, plain and with a tool call.
- `scripts/healthcheck.sh`: calls every group through the proxy; `--chain` checks the two entry points.
- `/update-chain` (`.agents/commands/update-chain.md`): the whole refresh, from scout to commit. Run it weekly.
- `docs/log.md`: dated work log, newest first. Add an entry for every change.

Hard rules: free tiers only, never spend money (no card, top-up, paid plan or recharge, not even a one-off to raise
a free limit); one account per provider; keys only in `.env` (never committed, never printed). Commit after each
change.

Clients: Kilo and OpenCode (`~/.config/kilo/kilo.jsonc`, `~/.config/opencode/opencode.jsonc`, model `litellm/coder`,
key file `~/reportaday/secrets/litellm_master_key`) and reportaday (`LITELLM_MODEL=pipeline`). Renaming `coder` or
`pipeline` breaks them; other group names are free to change, but Kilo's config lists some for manual picks.
