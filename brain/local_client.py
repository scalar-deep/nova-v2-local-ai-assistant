import httpx


class LocalAIClient:
    def __init__(self, base_url="http://localhost:11434", model="smollm2:135m"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def ask(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are Nova-V2, a local voice robot assistant. "
                        "Answer briefly and clearly. "
                        "Use simple words. "
                        "Keep answers under two sentences."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 60
            }
        }

        response = httpx.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=120,
        )
        response.raise_for_status()

        data = response.json()
        return data["message"]["content"].strip()
