"""A tiny client for Ollama's local HTTP API.

We ask Ollama to fill in the code at the cursor: given the code before the
cursor (the "prefix") and the code after it (the "suffix"), return a plausible
continuation of the current line. This module keeps all of that networking
logic in one place, using nothing but the standard library so the project has
no third-party dependencies.

Code-completion models such as Qwen2.5-Coder are trained for "fill in the
middle" (FIM): you show them the prefix and suffix wrapped in special tokens
and they generate the missing middle. That is exactly our situation, so we use
it rather than a natural-language instruction, which base code models follow
poorly.
"""

import json
import urllib.error
import urllib.request

import config


def request_completion(prefix, suffix=""):
    """Return a single-line completion for the gap between prefix and suffix.

    `prefix` is the code immediately before the cursor and `suffix` the code
    immediately after it. We return a single-line string (never containing a
    newline) to insert at the cursor. On any failure -- server down, timeout,
    bad response -- we return an empty string rather than raising, because a
    missing suggestion is never worth interrupting the user's typing over.
    """
    body = _build_request_body(prefix, suffix)
    try:
        raw_text = _post(config.OLLAMA_URL + "/api/generate", body)
    except (urllib.error.URLError, TimeoutError, OSError):
        # Network problems are expected (server not started yet, etc.). We treat
        # them as "no suggestion available" rather than crashing the editor.
        return ""

    return _clean_completion(raw_text)


def _build_request_body(prefix, suffix):
    """Assemble the JSON payload Ollama's /api/generate endpoint expects.

    We hand the model a fill-in-the-middle prompt built from the FIM tokens in
    config, and set `raw` so Ollama sends our prompt verbatim instead of wrapping
    it in a chat template (which would break the FIM format). The `stop` tokens
    keep the answer to a single line and prevent the model running past it.
    """
    fim_prompt = (
        config.FIM_PREFIX + prefix
        + config.FIM_SUFFIX + suffix
        + config.FIM_MIDDLE
    )

    return {
        "model": config.MODEL,
        "prompt": fim_prompt,
        "raw": True,      # Send the prompt as-is; do not apply a chat template.
        "stream": False,  # We want the whole answer in one response, not chunks.
        "options": {
            "temperature": config.TEMPERATURE,
            "num_predict": config.MAX_TOKENS,
            "stop": config.STOP_TOKENS,
        },
    }


def _post(url, body):
    """Send `body` as JSON to `url` and return the model's `response` text."""
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=config.REQUEST_TIMEOUT) as response:
        payload = json.loads(response.read().decode("utf-8"))

    # Ollama returns the generated text under the "response" key.
    return payload.get("response", "")


def _clean_completion(text):
    """Tidy up the model's raw output into something safe to insert inline.

    With FIM the model returns just the missing code, but we still guard against
    a stray newline or leftover special token slipping through.
    """
    # Keep only the first line: our stop token usually handles this, but a model
    # may still emit a newline in some cases.
    text = text.split("\n", 1)[0]

    # Remove any FIM special tokens the model may have echoed.
    for token in (config.FIM_PREFIX, config.FIM_SUFFIX, config.FIM_MIDDLE):
        text = text.replace(token, "")

    # Trailing whitespace is never useful in a suggestion; leading whitespace
    # can be (e.g. indentation), so we only strip the right side.
    return text.rstrip()
