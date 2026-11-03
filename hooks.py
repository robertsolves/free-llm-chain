"""LiteLLM proxy hook: normalise coding-tool requests so every free provider accepts them.

Kilo and OpenCode send message content as lists of text parts on some messages and plain strings on
others. Cloudflare Workers AI rejects that mix ("Type mismatch of '/messages/0/content'"), so text-only
lists are joined into plain strings, which every provider accepts.
"""

from litellm.integrations.custom_logger import CustomLogger


def _flatten(content):
    if isinstance(content, list) and all(isinstance(p, dict) and p.get("type") == "text" for p in content):
        return "".join(p.get("text", "") for p in content)
    return content


class Normalise(CustomLogger):
    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        for message in data.get("messages") or []:
            if "content" in message:
                message["content"] = _flatten(message["content"])
            if message.get("role") == "assistant" and message.get("content") is None:
                message["content"] = ""  # Cloudflare requires content even beside tool_calls
        return data


normalise = Normalise()
