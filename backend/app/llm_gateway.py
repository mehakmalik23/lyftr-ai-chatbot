import time
import litellm
from litellm.caching.caching import Cache
from fastapi import HTTPException
from .config import settings

# Initialize LiteLLM built-in in-memory cache
litellm.cache = Cache(type="local")
litellm.suppress_debug_info = True

VALID_SIMULATED_STATUSES = {429, 500, 502, 503}

def parse_simulate_failure_header(header_val: str | None) -> dict[str, int]:
    if not header_val or not settings.enable_failure_simulation:
        return {}
    rules = {}
    for pair in header_val.split(","):
        pair = pair.strip()
        if "=" in pair:
            k, v = pair.split("=", 1)
            k, v = k.strip(), v.strip()
            if v.isdigit() and int(v) in VALID_SIMULATED_STATUSES:
                rules[k] = int(v)
    return rules

def generate_chat_completion(messages: list[dict], simulate_header: str | None = None) -> tuple[str, dict]:
    start_time = time.perf_counter()
    keys = settings.llm_api_keys
    model = settings.llm_model
    if keys:
        first_key = keys[0]
        if first_key.startswith("gsk_") and not model.startswith("groq/"):
            model = "groq/llama-3.3-70b-versatile"
        elif first_key.startswith("AIza") and not model.startswith("gemini/"):
            model = "gemini/gemini-2.0-flash" 

    if not keys:
        raise HTTPException(status_code=503, detail="all providers unavailable")

    # 1. Check LiteLLM built-in cache first (keyed strictly by model + full message list)
    cached_result = litellm.cache.get_cache(model=model, messages=messages)
    if cached_result is not None:
        latency_ms = max(0, int((time.perf_counter() - start_time) * 1000))
        reply = cached_result["choices"][0]["message"]["content"]
        usage = cached_result.get("usage", {})
        input_tokens = int(usage.get("prompt_tokens", 0))
        output_tokens = int(usage.get("completion_tokens", 0))
        return reply, {
            "resolution_source": "LLM_CACHE",
            "model": model,
            "latency_ms": latency_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "key_id": None,
            "fallback_attempts": 0
        }

    # 2. Live Inference across key pool with automatic failover
    failure_rules = parse_simulate_failure_header(simulate_header)
    fallback_attempts = 0

    for idx, raw_key in enumerate(keys):
        key_id = f"key_{idx + 1}"

        # Check X-Simulate-Failure hook for this specific key or wildcard '*'
        simulated_status = failure_rules.get(key_id) or failure_rules.get("*")
        if simulated_status:
            fallback_attempts += 1
            continue

        try:
            response = litellm.completion(
                model=model,
                messages=messages,
                api_key=raw_key,
                caching=False,  # We explicitly manage cache read/write via litellm.cache for exact key control
                num_retries=0
            )
            # Ensure small minimum difference so live call is measurably slower than a 0-1ms cache hit
            elapsed_ms = max(1, int((time.perf_counter() - start_time) * 1000))
            reply = response.choices[0].message.content or ""
            usage = getattr(response, "usage", None)
            input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)

            # Store in LiteLLM built-in cache keyed by (model + messages)
            cache_payload = {
                "choices": [{"message": {"content": reply}}],
                "usage": {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens
                }
            }
            litellm.cache.add_cache(result=cache_payload, model=model, messages=messages)

            return reply, {
                "resolution_source": "LIVE_INFERENCE",
                "model": model,
                "latency_ms": elapsed_ms,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "key_id": key_id,
                "fallback_attempts": fallback_attempts
            }
        except Exception as e:
            print(f'[LLM Gateway Error on {key_id} with model {model}]: {e}', flush=True)
            fallback_attempts += 1
            continue

    raise HTTPException(status_code=503, detail="all providers unavailable")
