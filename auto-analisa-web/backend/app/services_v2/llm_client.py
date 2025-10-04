import os
import httpx
import json


class LlmClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.model = model or os.getenv("MODEL_RESPONSES", os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))

    async def structured_response(self, system: str, user: str, json_schema: dict) -> dict:
        """Call Responses API (HTTP) to request strict JSON output via json_schema."""
        url = f"{self.base_url}/responses"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "AutoAnalisaV2", "schema": json_schema, "strict": True},
            },
        }
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            # Responses API returns a structured envelope; try to extract text
            try:
                content = data["output"]["content"][0]["text"]
            except Exception:
                content = data
            if isinstance(content, str):
                return json.loads(content)
            return content
