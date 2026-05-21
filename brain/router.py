"""
Main routing logic - single LLM for routing and chat.
Includes text-based tool detection fallback for smaller models.
"""

import re
from typing import Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from .ollama_client import OllamaClient, ChatResponse
from .tool_definitions import TOOLS, SYSTEM_PROMPT


class ToolType(Enum):
    TIME = "get_current_time"
    WEATHER = "get_weather"
    NEWS = "get_news"
    SYSTEM_STATUS = "get_system_status"
    JOKE = "get_joke"
    CLOUD = "cloud_handoff"
    NONE = "none"  # Direct chat response


@dataclass
class RouterResult:
    """Result from the router."""
    tool: ToolType
    response: Optional[str]  # Direct response if no tool
    arguments: dict  # Tool arguments if tool called


class Router:
    """Routes user queries to appropriate handlers."""

    # Keywords for text-based tool detection (using word boundary matching)
    TIME_PHRASES = ["what time", "what's the time", "current time", "what day is it", "what's the date", "what date"]
    WEATHER_PHRASES = ["weather in", "weather for", "what's the weather", "how's the weather", "temperature in", "weather now", "weather today"]
    NEWS_PHRASES = ["news", "headlines", "what's happening", "whats happening", "current events", "top stories"]
    SYSTEM_PHRASES = ["system status", "how are you doing", "how are you feeling", "your temperature", "cpu temp", "health check", "how's your health", "how you doing"]
    JOKE_PHRASES = ["tell me a joke", "joke", "make me laugh", "something funny", "say something funny"]
    FACT_PHRASES = ["something", "something new", "tell me something new", "tell me a fact", "interesting fact", "say something interesting"]
    IDENTITY_PHRASES = ["how old are you", "what is your age", "who are you", "what are you", "what do you do", "what can you do", "where do you live", "where are you from"]
    WELLBEING_PHRASES = ["how are you", "how about you", "what about you", "are you okay", "how do you feel", "are you doing okay"]
    LOCATION_UNKNOWN_PHRASES = ["where is", "where are"]
    MOOD_PHRASES = ["i am happy", "im happy", "i feel happy", "i am sad", "im sad", "i feel sad"]

    # Phrases that the local model can handle — simple chat, greetings, identity
    LOCAL_PHRASES = [
        "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
        "how are you", "what's up", "who are you", "what are you", "what's your name",
        "thank you", "thanks", "bye", "goodbye", "see you", "good night",
        "help", "what can you do",
    ]

    def __init__(self, ollama_client: OllamaClient):
        self.client = ollama_client
        self.conversation_history = []

    def _is_local_chat(self, user_input: str) -> bool:
        """Check if the input is simple enough for the local model."""
        user_lower = user_input.lower().strip()
        # Short greetings / simple chat
        for phrase in self.LOCAL_PHRASES:
            if phrase in user_lower:
                return True
        # Very short inputs (1-3 words) that aren't questions are likely greetings
        words = user_lower.split()
        if len(words) <= 3 and "?" not in user_input:
            return True
        return False

    def _extract_news_category(self, user_input: str) -> str:
        """Extract news category from user input."""
        user_lower = user_input.lower()
        categories = ["business", "entertainment", "health", "science", "sports", "technology"]
        # Also match common synonyms
        synonyms = {"tech": "technology", "sport": "sports", "medical": "health"}
        for synonym, category in synonyms.items():
            if synonym in user_lower:
                return category
        for cat in categories:
            if cat in user_lower:
                return cat
        return ""

    def _detect_tool_from_text(self, user_input: str, response_text: str) -> Tuple[ToolType, dict]:
        """
        Detect tool from user input keywords and/or model response text.
        Fallback for models that don't use structured tool calls.
        """
        user_lower = user_input.lower()
        response_lower = (response_text or "").lower()

        # Priority 1: Check for tool mentions in model response (e.g., "[get_current_time]")
        if "get_current_time" in response_lower:
            return ToolType.TIME, {}

        if "get_weather" in response_lower:
            location = self._extract_location(user_input, response_text)
            return ToolType.WEATHER, {"location": location}

        if "get_news" in response_lower:
            category = self._extract_news_category(user_input)
            return ToolType.NEWS, {"category": category}

        if "get_system_status" in response_lower:
            return ToolType.SYSTEM_STATUS, {}

        if "get_joke" in response_lower:
            return ToolType.JOKE, {}

        if "cloud_handoff" in response_lower:
            return ToolType.CLOUD, {"query": user_input}

        # Priority 2: Check for specific phrases in user input
        for phrase in self.TIME_PHRASES:
            if phrase in user_lower:
                return ToolType.TIME, {}

        for phrase in self.WEATHER_PHRASES:
            if phrase in user_lower:
                location = self._extract_location(user_input, "")
                return ToolType.WEATHER, {"location": location}

        for phrase in self.NEWS_PHRASES:
            if phrase in user_lower:
                category = self._extract_news_category(user_input)
                return ToolType.NEWS, {"category": category}

        for phrase in self.JOKE_PHRASES:
            if phrase in user_lower:
                return ToolType.JOKE, {}

        for phrase in self.SYSTEM_PHRASES:
            if phrase in user_lower:
                return ToolType.SYSTEM_STATUS, {}

        # Priority 3: If it's simple chat, keep local

        if self._is_local_chat(user_input):
            return ToolType.NONE, {}

        # Priority 4: Everything else → cloud handoff
        # The local 1.5B model can't reliably answer knowledge/technical questions
        return ToolType.CLOUD, {"query": user_input}

    def _extract_location(self, user_input: str, response_text: str) -> str:
        """Extract location from user input or response."""
        # Try to find location in model response
        match = re.search(r'location["\s=:]+["\']*([^"\'\]\s,]+)', response_text, re.IGNORECASE)
        if match:
            return match.group(1)

        # Try common patterns in user input
        patterns = [
            r"weather (?:in|for|at) ([A-Za-z\s]+)",
            r"in ([A-Za-z]+)",
            r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)"  # Capitalized words
        ]

        for pattern in patterns:
            match = re.search(pattern, user_input)
            if match:
                loc = match.group(1).strip()
                # Filter out common words
                if loc.lower() not in ["the", "is", "it", "what", "how", "like"]:
                    return loc

        return ""  # No location found, orchestrator will use config default

    def route(self, user_input: str) -> RouterResult:
        lowered = user_input.lower().strip().rstrip(".!?")
        mood_lowered = lowered.replace("'", "")
        if any(phrase in mood_lowered for phrase in self.MOOD_PHRASES):
            print("[router] deterministic mood")
            if "sad" in mood_lowered:
                return RouterResult(
                    tool=ToolType.NONE,
                    response="I am here with you. We can take it one step at a time.",
                    arguments={}
                )
            return RouterResult(
                tool=ToolType.NONE,
                response="That is good to hear. I like seeing you happy.",
                arguments={}
            )

        if any(lowered.startswith(phrase) for phrase in self.LOCATION_UNKNOWN_PHRASES):
            print("[router] deterministic unknown location")
            return RouterResult(
                tool=ToolType.NONE,
                response="I do not know where they are. I should not guess.",
                arguments={}
            )

        if any(phrase in lowered for phrase in self.WELLBEING_PHRASES):
            print("[router] deterministic wellbeing")
            return RouterResult(
                tool=ToolType.NONE,
                response="I'm doing well. Just keeping an eye on things here.",
                arguments={}
            )

        if any(phrase in lowered for phrase in self.IDENTITY_PHRASES):
            print("[router] deterministic identity")
            if "old" in lowered or "age" in lowered:
                return RouterResult(
                    tool=ToolType.NONE,
                    response="I do not have a human age. I am Nova-V2, running locally on this Raspberry Pi.",
                    arguments={}
                )
            return RouterResult(
                tool=ToolType.NONE,
                response="I am Nova-V2, your local companion assistant. I can talk, remember important things, react with my face, and take pictures when you ask.",
                arguments={}
            )

        if any(phrase in lowered for phrase in self.FACT_PHRASES):
            print("[router] deterministic fact")
            return RouterResult(
                tool=ToolType.NONE,
                response="Octopuses have three hearts, and two of them slow down when they swim.",
                arguments={}
            )

        """
        Route user input to appropriate handler.
        """
        user_lower = user_input.lower().strip().rstrip(".!?")

        quick_replies = {
            "hello": "Hello.",
            "hi": "Hi.",
            "hey": "Hey.",
            "okay": "Okay.",
            "ok": "Okay.",
            "alright": "Alright.",
            "cool": "Cool.",
            "yes": "Yes.",
            "no": "No.",
            "thanks": "You're welcome.",
            "thank you": "You're welcome.",
            "bye": "Goodbye.",
            "goodbye": "Goodbye.",
            "see you": "See you.",
            "good night": "Good night.",
        }

        if user_lower in quick_replies:
            self.conversation_history.append(
                {"role": "user", "content": user_input}
            )
            self.conversation_history.append(
                {"role": "assistant", "content": quick_replies[user_lower]}
            )
            return RouterResult(
                tool=ToolType.NONE,
                response=quick_replies[user_lower],
                arguments={}
            )

        # Deterministic routing before calling the tiny local model.
        tool_type, arguments = self._detect_tool_from_text(user_input, "")

        if tool_type != ToolType.NONE and tool_type != ToolType.CLOUD:
            self.conversation_history.append(
                {"role": "user", "content": user_input}
            )
            return RouterResult(
                tool=tool_type,
                response=None,
                arguments=arguments
            )

        # Build messages
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

        # Add conversation history (keep last 4 exchanges for context)
        messages.extend(self.conversation_history[-8:])

        # Add current user message
        messages.append({"role": "user", "content": user_input})

        # Get response with tool calling
        response = self.client.chat(messages, tools=None)

        # Process response
        if response.is_tool_call:
            # Model used structured tool calling
            tool_call = response.tool_calls[0]

            try:
                tool_type = ToolType(tool_call.name)
            except ValueError:
                tool_type = ToolType.NONE

            self.conversation_history.append(
                {"role": "user", "content": user_input}
            )

            return RouterResult(
                tool=tool_type,
                response=None,
                arguments=tool_call.arguments
            )
        else:
            # Fallback: detect tool from text
            tool_type, arguments = self._detect_tool_from_text(
                user_input, response.content
            )

            self.conversation_history.append(
                {"role": "user", "content": user_input}
            )

            if tool_type == ToolType.NONE:
                # Simple chat — use the local model's response
                self.conversation_history.append(
                    {"role": "assistant", "content": response.content or ""}
                )
                return RouterResult(
                    tool=ToolType.NONE,
                    response=response.content,
                    arguments={}
                )
            else:
                # Tool or cloud handoff
                return RouterResult(
                    tool=tool_type,
                    response=None,
                    arguments=arguments
                )

    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
