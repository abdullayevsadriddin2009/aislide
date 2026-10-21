API_LIST = [
    {
        "name": "Groq 1 (asosiy)",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.getenv("GROQ_KEY_1", ""),
        "type": "openai",
        "models": [
            "qwen/qwen3.8-27b",
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b"
        ]
    },
    {
        "name": "Groq 2",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.getenv("GROQ_KEY_2", ""),
        "type": "openai",
        "models": [
            "qwen/qwen3.8-27b",
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b"
        ]
    },
   {"name": "Cloudflare AI (zaxira)",
     "base_url": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run",
     "account_id": os.getenv("CLOUDFLARE_ACCOUNT_ID", ""),
     "api_key": os.getenv("CLOUDFLARE_KEY", ""), "type": "cloudflare",
     "models": ["@cf/meta/llama-3-8b-instruct", "@cf/meta/llama-3.1-8b-instruct",
                "@cf/mistral/mistral-7b-instruct-v0.2", "@cf/google/gemma-7b-it-lora"]},
    {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": os.getenv("OPENROUTER_KEY", ""),
        "type": "openai",
        "models": [
            "qwen/qwen3.8-27b",
            "openai/gpt-oss-120b",
            "meta-llama/llama-3.2-3b-instruct"
        ]
    },
    {
        "name": "Google AI",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "api_key": os.getenv("GOOGLE_KEY_1", ""),
        "type": "google",
        "models": [
            "gemini-2.0-flash-exp",
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b"
        ]
    },
    {
        "name": "Local FreeLLMAPI",
        "base_url": AI_API_URL,
        "api_key": os.getenv("AI_API_KEY", ""),
        "type": "openai",
        "models": [AI_MODEL, "gpt-3.5-turbo", "llama3"]
    },
]

CURRENT_API_INDEX = 0
CURRENT_MODEL_INDEX = 0
