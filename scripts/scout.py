#!/usr/bin/env python3
"""Scout the free providers for changes to the chain in config.yaml. Standard library only.

    python3 scripts/scout.py                 # report: gone models, new candidates, quotas, recent 429s
    python3 scripts/scout.py probe <model>   # call one model directly, plain and with a tool, e.g.
                                             #   probe gemini/gemini-3.5-flash
                                             #   probe openrouter/qwen/qwen3-coder:free

Reads provider keys from .env. Prints model ids in LiteLLM form (provider/model), ready for config.yaml.
Never prints keys.
"""

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config.yaml"
REJECTED = ROOT / "rejected.txt"
CONTAINER = os.environ.get("LITELLM_CONTAINER", "free-llm-chain")

# How each provider counts its free quota. "model": every model has its own daily pool, so adding a model
# adds volume. "account": all models share one pool, so another model only adds a fallback when one is down.
POOLS = {"gemini": "model", "groq": "model", "zai": "model", "openrouter": "account", "cloudflare": "account"}

# Families that never belong in a text chain (speech, images, guards, embeddings).
# Providers whose model listing leaves out models they still serve (Z.ai omits its free -flash models),
# so a configured model missing from the listing is not proof it is gone: probe it instead.
INCOMPLETE_LISTING = {"zai"}

SKIP = re.compile(r"tts|image|embed|whisper|orpheus|guard|safeguard|lyria|banana|aqa|imagen|veo|live|audio|"
                  r"deep-research|allam|robotics|computer-use|transcribe|lora|micro|-[13]b-", re.I)


def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            m = re.match(r"\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)", line)
            if m and m.group(1) not in os.environ:
                os.environ[m.group(1)] = m.group(2).split(" #")[0].strip().strip('"').strip("'")


def http(url, key=None, body=None, timeout=60, headers=None):
    """Returns (status, parsed JSON or text)."""
    h = {"Content-Type": "application/json", "User-Agent": "free-llm-chain-scout"}
    if key:
        h["Authorization"] = f"Bearer {key}"
    h.update(headers or {})
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw, status = r.read().decode(), r.status
    except urllib.error.HTTPError as e:
        raw, status = e.read().decode(errors="replace"), e.code
    except Exception as e:  # timeouts and DNS: report, don't crash the whole scout
        return 0, f"{type(e).__name__}: {e}"
    try:
        return status, json.loads(raw)
    except ValueError:
        return status, raw


def configured():
    """{litellm model id: model group} from config.yaml, plus the Cloudflare api_base."""
    text = CONFIG.read_text()
    models, group, cf_base = {}, None, None
    for line in text.splitlines():
        if m := re.match(r"\s*- model_name:\s*(\S+)", line):
            group = m.group(1)
        elif m := re.match(r"\s*model:\s*(\S+)", line):
            models[m.group(1)] = group
        elif m := re.match(r"\s*api_base:\s*(https://api\.cloudflare\.com\S+)", line):
            cf_base = m.group(1)
    return models, cf_base


def rejected():
    """{model id: "date  reason"} from rejected.txt."""
    out = {}
    for line in REJECTED.read_text().splitlines() if REJECTED.exists() else []:
        if line.strip() and not line.startswith("#"):
            model, _, rest = line.strip().partition("  ")
            out[model] = rest.strip()
    return out


def provider_of(model_id):
    if model_id.startswith("openai/@cf/"):
        return "cloudflare"
    return model_id.split("/", 1)[0]


def chat_target(model_id, cf_base):
    """(url, key, bare model name) for a direct OpenAI-compatible call."""
    p, name = provider_of(model_id), model_id.split("/", 1)[1]
    if p == "gemini":
        return "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", os.environ.get("GEMINI_API_KEY"), name
    if p == "openrouter":
        return "https://openrouter.ai/api/v1/chat/completions", os.environ.get("OPENROUTER_API_KEY"), name
    if p == "groq":
        return "https://api.groq.com/openai/v1/chat/completions", os.environ.get("GROQ_API_KEY"), name
    if p == "zai":
        return "https://api.z.ai/api/paas/v4/chat/completions", os.environ.get("ZAI_API_KEY"), name
    if p == "cloudflare":
        return f"{cf_base}/chat/completions", os.environ.get("CLOUDFLARE_API_KEY"), name
    raise SystemExit(f"unknown provider in {model_id}: add it to scout.py")


def list_models(cf_base):
    """{provider: [litellm model ids]} that each provider serves to this account now."""
    out = {}
    if k := os.environ.get("GEMINI_API_KEY"):
        s, d = http(f"https://generativelanguage.googleapis.com/v1beta/models?pageSize=200&key={k}")
        if s == 200:
            out["gemini"] = ["gemini/" + m["name"].split("/", 1)[1] for m in d.get("models", [])
                             if "generateContent" in m.get("supportedGenerationMethods", [])]
    s, d = http("https://openrouter.ai/api/v1/models")
    if s == 200:
        out["openrouter"] = ["openrouter/" + m["id"] for m in d["data"] if m["id"].endswith(":free")
                             and m.get("context_length", 0) >= 32000
                             and "tools" in (m.get("supported_parameters") or [])]
    if k := os.environ.get("GROQ_API_KEY"):
        s, d = http("https://api.groq.com/openai/v1/models", k)
        if s == 200:
            out["groq"] = ["groq/" + m["id"] for m in d["data"] if m.get("active", True)]
    if k := os.environ.get("ZAI_API_KEY"):
        s, d = http("https://api.z.ai/api/paas/v4/models", k)
        if s == 200:
            # Z.ai lists paid models too; only the -flash ones are free.
            out["zai"] = ["zai/" + m["id"] for m in d["data"] if "flash" in m["id"]]
    if (k := os.environ.get("CLOUDFLARE_API_KEY")) and cf_base:
        base = cf_base.removesuffix("/ai/v1")
        s, d = http(f"{base}/ai/models/search?task=Text%20Generation&per_page=200", k)
        if s == 200:
            out["cloudflare"] = ["openai/" + m["name"] for m in d.get("result", [])]
    return out


def recent_429s():
    """Rate-limit errors in the last 24h from the proxy's container log, as two counts:
    {provider: 429s} (one model hit its limit) and {group: requests that failed on every fallback}."""
    try:
        log = subprocess.run(["docker", "logs", "--since", "24h", CONTAINER], capture_output=True,
                             text=True, timeout=60)
    except Exception:
        return None
    if log.returncode != 0:
        return None
    limited, exhausted = {}, {}
    for line in (log.stdout + log.stderr).splitlines():
        if "RateLimitError" in line and (m := re.search(r"(\w+)Exception", line)):
            p = m.group(1).lower().replace("openai", "cloudflare")
            limited[p] = limited.get(p, 0) + 1
        if "No deployments available" in line and (m := re.search(r"Passed model=([a-z0-9-]+)", line)):
            exhausted[m.group(1)] = exhausted.get(m.group(1), 0) + 1
    return limited, exhausted


def report():
    load_env()
    have, cf_base = configured()
    served = list_models(cf_base)
    print("# Scout report\n")

    print("## Configured models the provider no longer lists (replace these)")
    gone = [m for m in have if provider_of(m) in served and m not in served[provider_of(m)]
            and provider_of(m) not in INCOMPLETE_LISTING]
    print("\n".join(f"- {m} (group {have[m]})" for m in gone) or "- none")

    print("\n## Candidates not in config.yaml or rejected.txt (probe each before adding)")
    skipped = rejected()
    for p, ids in sorted(served.items()):
        new = [m for m in ids if m not in have and m not in skipped and not SKIP.search(m)]
        if new:
            note = "own daily pool each: adds volume" if POOLS.get(p) == "model" else "shared account pool: adds a fallback only"
            print(f"\n### {p} ({note})")
            print("\n".join(f"- {m}" for m in sorted(new)))
    print(f"\n({len(skipped)} models hidden by rejected.txt; re-probe lines older than 30 days)")
    missing = [p for p in POOLS if p not in served]
    if missing:
        print(f"\n(no listing from: {', '.join(missing)}: key missing or provider down)")

    print("\n## Quotas")
    if k := os.environ.get("OPENROUTER_API_KEY"):
        s, d = http("https://openrouter.ai/api/v1/key", k)
        if s == 200:
            q = d["data"].get("free_model_daily_requests") or {}
            print(f"- OpenRouter free requests today: {q.get('used')}/{q.get('limit')} used")
    print("- Gemini, Groq, Z.ai, Cloudflare publish no quota endpoint: see the 429 counts below.")

    print("\n## Last 24h from the proxy log")
    counts = recent_429s()
    if counts is None:
        print(f"- no log (container {CONTAINER} not running, or no docker)")
    else:
        for title, c in zip(("429s by provider (a pool ran dry)", "Requests that failed on every fallback, by group (add capacity here)"), counts):
            print(f"\n### {title}")
            print("\n".join(f"- {k}: {n}" for k, n in sorted(c.items(), key=lambda x: -x[1])) or "- none")


def probe(model_id):
    load_env()
    _, cf_base = configured()
    url, key, name = chat_target(model_id, cf_base)
    if not key:
        raise SystemExit(f"no key in .env for {provider_of(model_id)}")
    plain = {"model": name, "messages": [{"role": "user", "content": "Reply with the word OK."}], "max_tokens": 400}
    tool = {"model": name, "max_tokens": 400,
            "messages": [{"role": "user", "content": "List the files in /tmp. Use the tool."}],
            "tools": [{"type": "function", "function": {
                "name": "bash", "description": "Run a shell command",
                "parameters": {"type": "object", "properties": {"command": {"type": "string"}},
                               "required": ["command"]}}}]}
    ok = True
    for label, body in (("plain", plain), ("tools", tool)):
        s, d = http(url, key, body, timeout=90)
        msg = d["choices"][0]["message"] if s == 200 and isinstance(d, dict) and d.get("choices") else None
        if msg is None:
            print(f"FAIL  {label}: HTTP {s} {str(d)[:200]}")
            ok = False
        elif label == "tools" and not msg.get("tool_calls"):
            print(f"FAIL  tools: answered without a tool call: {str(msg.get('content'))[:120]!r}")
            ok = False
        else:
            content = str(msg.get("content") or "")
            leak = " (WARNING: thinking text in the reply)" if re.search(r"<think|<thought", content) else ""
            print(f"OK    {label}{leak}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "probe":
        probe(sys.argv[2])
    elif len(sys.argv) == 1:
        report()
    else:
        raise SystemExit(__doc__)
