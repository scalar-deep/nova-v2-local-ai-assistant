"""
News tool - fetches top headlines from NewsAPI.
"""

import httpx
from typing import Optional
import os


class NewsTool:
    """Fetches top news headlines from NewsAPI."""

    BASE_URL = "https://newsapi.org/v2/top-headlines"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("NEWSAPI_KEY")
        if not self.api_key:
            raise ValueError("NewsAPI key required")
        self.client = httpx.Client(timeout=10.0)

    def get_news(self, category: str = "") -> str:
        """
        Get top news headlines.

        Args:
            category: Optional category (business, entertainment, health,
                      science, sports, technology). Empty for general news.

        Returns:
            Natural language news summary for speech.
        """
        try:
            params = {
                "apiKey": self.api_key,
                "country": "us",
                "pageSize": 5,
            }
            if category and category.lower() in (
                "business", "entertainment", "health",
                "science", "sports", "technology",
            ):
                params["category"] = category.lower()

            response = self.client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()

            articles = data.get("articles", [])
            if not articles:
                return "I couldn't find any news headlines right now."

            # Build speech-friendly summary
            lines = []
            for i, article in enumerate(articles[:5], 1):
                title = article.get("title", "").split(" - ")[0].strip()
                if title:
                    lines.append(f"{i}. {title}")

            if not lines:
                return "I couldn't find any news headlines right now."

            cat_label = f" {category}" if category else ""
            intro = f"Here are the top{cat_label} headlines. "
            return intro + ". ".join(lines) + "."

        except Exception as e:
            return f"Sorry, I couldn't fetch the news right now. {str(e)}"
