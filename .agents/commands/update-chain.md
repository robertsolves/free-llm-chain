---
description: "Keep the free model chain healthy and growing: replace models providers retired, probe every new free model and add the ones that work, look for new free providers, then restart the proxy, check it, log and commit. Run weekly, whenever healthcheck reports a FAIL, or when Kilo or the pipeline keep running out of models. Free tiers only: never add anything that asks for payment."
argument-hint: "[--no-research]"
---

# /update-chain

The goal is as much free daily capacity as possible, for coding (`coder`) and small prompts (`pipeline`). More models means more volume only where a provider gives each model its own daily pool; read the pool notes at the top of `config.yaml` before deciding where a model goes.

Writes: `config.yaml`, `rejected.txt`, `.env.example` (new providers only), `docs/log.md`, one commit. Never writes `.env` or prints a key.

Hard rule: free only. If a provider, model or step asks for a card, a top-up, a paid plan or a recharge, it goes into `rejected.txt` and nothing is changed for it. That includes one-off payments that raise free limits.

## Step 1: Read the current state

```sh
python3 scripts/scout.py
```

Done when: you have the report. If the proxy log section says no container is running, start it: `docker compose up -d`. If this repo is a submodule inside another project, the container may have another name: set `LITELLM_CONTAINER=<name>` and rerun.

## Step 2: Re-probe old rejections

For each line in `rejected.txt` dated more than 30 days ago:

```sh
python3 scripts/scout.py probe <model id>
```

| Probe result | Do this |
|---|---|
| `OK plain` and `OK tools` | Delete the line. The model becomes a candidate in Step 4. |
| Fails for the same reason | Change the line's date to today. |
| Fails for a new reason | Update the date and the reason. |

Done when: no line in `rejected.txt` is older than 30 days.

## Step 3: Replace retired models

For each model under "Configured models the provider no longer lists", and each healthcheck FAIL that is not a 429 or quota error (`bash scripts/healthcheck.sh`):

1. Probe it once (`python3 scripts/scout.py probe <model id>`). A provider listing can lag.
2. Still failing: delete its `model_list` entry and its name from every `fallbacks` list, then add it to `rejected.txt` with today's date and the error.

Done when: every configured model either probes OK or has been removed.

## Step 4: Probe every candidate

Run every model under "Candidates" through a probe (eight at a time is fine):

```sh
python3 scripts/scout.py probe <model id>
```

| Probe result | Do this |
|---|---|
| `OK plain` and `OK tools` | Add it (Step 5). |
| `OK plain` only | Add it to the `pipeline` lane only (no tools needed there). |
| Thinking-text warning | Reject: the pipeline parses JSON and coding tools choke on the stray text. |
| 403 or "paid plan", "upgrade", "balance", "recharge" | Reject: not free. |
| 404, "no longer available", "Interactions API only" | Reject. |
| 429, 503, timeout | Probe once more. Still failing: reject with "retry later". Those come back in 30 days. |
| An alias (`*-latest`) of a model already configured | Reject: it shares that model's pool. |

Each OpenRouter probe uses 2 of the account's 50 free requests a day. Probe the OpenRouter models after the others, and stop probing them if the report shows fewer than 15 left.

Done when: every candidate is either added or in `rejected.txt`.

## Step 5: Add the working models

For each model to add:

1. Add a `model_list` entry under its provider's section, named `<provider>-<model>` in the style already there. Copy that provider's `timeout`/`stream_timeout` lines from its neighbours.
2. Put its name into the fallback lists:

| Model | `coder` list | `pipeline` list |
|---|---|---|
| Own-pool provider (Gemini, Groq, Z.ai), strong (Pro, Flash, coder) | In the provider block, ordered strongest first | no |
| Own-pool, weak (Lite, small) | In the tail, beside the other weak models | yes, at the end |
| Groq (any) | never: input is capped at 7-8k tokens a minute | yes |
| Shared-pool provider (OpenRouter, Cloudflare) | In that provider's block, as a fallback | never: it would spend coding's pool |
| `OK plain` only | no | yes |

Done when: every added model is in `model_list` and in at least one fallback list.

## Step 6: Look for new free providers

Skip this step if `$ARGUMENTS` contains `--no-research`.

Search the web for free LLM API tiers updated in the last two months (for example "free LLM API tiers <month> <year>", the cheahjs/free-llm-api-resources and mnfst/awesome-free-llm-apis lists). For every provider not already in `config.yaml` or the "Not used" notes there:

| What you find | Do this |
|---|---|
| Free forever, no card, OpenAI-compatible, a coding-capable model | Add it to `.env.example` with where to get the key, and list it under "New providers" in your report. Don't add it to `config.yaml`: it has no key yet. |
| A trial, a card at signup, real-name ID checks, non-commercial only | Add it to the "Not used" note at the top of `config.yaml` with the reason. |

A free tier whose terms forbid several accounts or keys per person: one account only. Never suggest working around a limit with more accounts or IPs.

Done when: every provider you found is either in `.env.example` or in the "Not used" note.

## Step 7: Restart and check

```sh
docker compose up -d --force-recreate litellm && sleep 10 && bash scripts/healthcheck.sh; bash scripts/healthcheck.sh --chain
```

| Result | Do this |
|---|---|
| `--chain` fails | Something in the YAML is broken. Run `docker logs free-llm-chain 2>&1 \| tail -40`, fix it and repeat this step. |
| A group fails with an error other than 429 or quota | Back to Step 3 for that model. |
| Only 429 or quota FAILs | Fine: those pools are used up for today. |

Done when: `--chain` passes and no FAIL is anything but a used-up pool.

## Step 8: Log and commit

Add an entry at the top of `docs/log.md` under today's date: models added, replaced and rejected, new providers waiting for keys, and the counts from the scout's "Last 24h" section. Update the date in the "Model IDs checked" line of `config.yaml`. Then:

```sh
git add -A && git commit -m "Chain: <one-line summary>"
```

End the commit message with the session's attribution lines, if any.

Done when: the commit exists. Report to the user, in this order: the commit's one-line summary, the counts of models added, replaced and rejected, and any new providers that need a key from them (with the signup URL).
