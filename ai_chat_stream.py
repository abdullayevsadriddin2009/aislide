"""CdxChatBot.php dagi `gemini_reply` mantiqining Python ko'rinishi.

Farqi: kalitlar va modellar admin paneldagi bazadan olinadi (ai_pool), javob esa
oqim (SSE) bilan keladi — `on_text` har safar hozirgacha yig'ilgan matn bilan
chaqiriladi. Xato bergan kalit `fails` hisoblagichini oshiradi va keyingi safar
ro'yxat oxiriga tushadi. Model topilmasa (404) keyingi modelga o'tiladi.
"""
import asyncio
import json

import aiohttp

import ai_pool

AI_TIMEOUT = 120
_CREDENTIAL_CODES = (400, 401, 403)
_MAX_ATTEMPTS = 14


def build_contents(history, prompt):
    """Suhbat tarixini Gemini `contents` shakliga o'giradi (tarix user'dan boshlanadi)."""
    contents = []
    for item in history or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("content") or "").strip()
        if not text:
            continue
        role = "model" if str(item.get("role") or "").lower() in ("assistant", "model") else "user"
        contents.append({"role": role, "parts": [{"text": text[:4000]}]})
    while contents and contents[0]["role"] != "user":
        contents.pop(0)
    contents.append({"role": "user", "parts": [{"text": str(prompt or "")}]})
    return contents


def _key_models(key):
    """Kalit uchun model nomlari: bazadagilar, bo'sh bo'lsa provayder zaxirasi."""
    names = [name.strip() for name in str(key.get("models") or "").split(",") if name.strip()]
    if names:
        return names
    return list(ai_pool.PROVIDER_MODELS.get(str(key.get("provider") or ""), ()))


def attempts():
    """[(kalit, model)] — asosiy modeldan boshlab, xatolar soni bo'yicha tartibda."""
    keys = ai_pool.keys(active_only=True)
    models = [row["name"] for row in ai_pool.models() if row["active"]]
    ordered = []
    if models:
        for model in models:
            for key in keys:
                names = _key_models(key)
                if names and model not in names:
                    continue
                ordered.append((key, model))
        # Admin belgilagan modellar ro'yxatiga kirmagan modellarni ham sinaymiz.
        for key in keys:
            for model in _key_models(key):
                if model not in models:
                    ordered.append((key, model))
    else:
        for key in keys:
            for model in _key_models(key):
                ordered.append((key, model))
    # Bir xil (kalit, model) juftligi ikki marta sinalmasin.
    unique, seen = [], set()
    for key, model in ordered:
        pair = (key.get("id"), model)
        if pair in seen:
            continue
        seen.add(pair)
        unique.append((key, model))
    return unique[:_MAX_ATTEMPTS]


def _body(system, contents, temperature, max_tokens):
    data = {
        "contents": contents,
        "generationConfig": {
            "temperature": float(temperature or 0.7),
            "maxOutputTokens": int(max_tokens or 1024),
        },
    }
    prompt = str(system or "").strip()
    if prompt:
        data["systemInstruction"] = {"parts": [{"text": prompt}]}
    return data


def _openai_messages(system, contents):
    messages = []
    if str(system or "").strip():
        messages.append({"role": "system", "content": str(system).strip()})
    for item in contents:
        role = "assistant" if item["role"] == "model" else "user"
        text = "".join(part.get("text", "") for part in item.get("parts") or [])
        if text.strip():
            messages.append({"role": role, "content": text})
    return messages


async def _stream_google(session, key, model, body, on_text):
    """Gemini `streamGenerateContent?alt=sse` — PHP dagi bilan bir xil so'rov."""
    base = str(key.get("base_url") or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    url = f"{base}/models/{model}:streamGenerateContent?alt=sse"
    headers = {"Content-Type": "application/json", "x-goog-api-key": str(key.get("api_key") or "")}
    text = ""
    async with session.post(url, json=body, headers=headers) as resp:
        if resp.status != 200:
            detail = await resp.text()
            return resp.status, None, _error_detail(detail, resp.status)
        buffer = ""
        async for raw in resp.content.iter_any():
            buffer += raw.decode("utf-8", "ignore")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip("\r")
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if not payload or payload == "[DONE]":
                    continue
                try:
                    event = json.loads(payload)
                except ValueError:
                    continue
                chunk = ""
                for part in ((event.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []:
                    chunk += part.get("text") or ""
                if chunk:
                    text += chunk
                    if on_text:
                        on_text(text)
    if text.strip():
        return 200, text, None
    return 200, None, "bo'sh javob (xavfsizlik filtri bo'lishi mumkin)"


async def _post_openai(session, key, model, messages, temperature, max_tokens):
    base = str(key.get("base_url") or ai_pool.PROVIDER_BASE.get(str(key.get("provider")), "")).rstrip("/")
    headers = {"Content-Type": "application/json",
               "Authorization": f"Bearer {key.get('api_key')}"}
    payload = {
        "model": model,
        "messages": messages,
        "temperature": float(temperature or 0.7),
        "max_tokens": int(max_tokens or 1024),
    }
    async with session.post(f"{base}/chat/completions", json=payload, headers=headers) as resp:
        raw = await resp.text()
        if resp.status != 200:
            return resp.status, None, _error_detail(raw, resp.status)
        try:
            message = json.loads(raw)["choices"][0]["message"]
        except Exception as exc:
            return resp.status, None, f"javob o'qilmadi: {exc}"
        content = str(message.get("content") or "").strip()
        if content:
            return 200, content, None
        return resp.status, None, "bo'sh javob (HTTP 200)"


def _error_detail(raw, status):
    try:
        data = json.loads(raw)
    except Exception:
        return f"HTTP {status}: {str(raw)[:180]}"
    detail = ((data.get("error") or {}).get("message")
              or (data.get("message") if isinstance(data, dict) else "")
              or (data[0].get("error", {}).get("message") if isinstance(data, list) and data else ""))
    return f"HTTP {status}: {str(detail or 'xato')[:180]}"


async def stream_reply(system, prompt, history=None, on_text=None,
                       temperature=0.7, max_tokens=1024):
    """Javobni oqim bilan oladi.

    Muvaffaqiyatli bo'lsa to'liq matn, aks holda None qaytaradi va sababni
    `ai_pool` dagi `last_error` ga yozadi.
    """
    contents = build_contents(history, prompt)
    body = _body(system, contents, temperature, max_tokens)
    messages = _openai_messages(system, contents)
    plan = attempts()
    if not plan:
        ai_pool.note_error("Faol API kalit yo'q (admin panel → AI)")
        return None

    last = ""
    attempts_made = 0
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=AI_TIMEOUT)) as session:
        for key, model in plan:
            attempts_made += 1
            key_id = key.get("id")
            label = f"{key.get('label') or key.get('provider')} / {model}"
            try:
                if str(key.get("provider")) == "google":
                    status, text, error = await _stream_google(session, key, model, body, on_text)
                else:
                    status, text, error = await _post_openai(
                        session, key, model, messages, temperature, max_tokens)
                    if status == 200 and text and on_text:
                        on_text(text)
            except Exception as exc:
                status, text, error = None, None, f"{type(exc).__name__}: {exc}"

            if status == 200 and text and text.strip():
                ai_pool.mark_result(key_id, True)
                ai_pool.note_error("")
                return text.strip()

            last = f"{label}: {error or 'javob kelmadi'}"
            print(f"[ai_chat] ❌ {last}", flush=True)
            if status == 404:
                break  # model topilmadi → keyingi model
            if status in _CREDENTIAL_CODES:
                ai_pool.mark_result(key_id, False)
            await asyncio.sleep(0)

    ai_pool.note_error(f"Barcha urinishlar muvaffaqiyatsiz ({attempts_made}): {last}")
    return None
