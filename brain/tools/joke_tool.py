"""
Joke tool - fetches random jokes from a free API.
"""

import httpx


def get_joke() -> str:
    """
    Fetch a random joke from the Official Joke API.

    Returns:
        A joke formatted for speech (setup + punchline).
    """
    try:
        client = httpx.Client(timeout=5.0)
        response = client.get(
            "https://official-joke-api.appspot.com/random_joke"
        )
        response.raise_for_status()
        data = response.json()

        setup = data.get("setup", "")
        punchline = data.get("punchline", "")

        if setup and punchline:
            return f"{setup} ... {punchline}"
        return "I tried to think of a joke, but my circuits got crossed."

    except Exception:
        return "Sorry, I couldn't fetch a joke right now. But you know what's funny? A Raspberry Pi trying to be a comedian."
