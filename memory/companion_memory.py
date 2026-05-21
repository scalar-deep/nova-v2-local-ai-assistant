import json
import time
from pathlib import Path


class CompanionMemory:
    def __init__(self, path="memory/memory.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.last_user_message = ""
        self.previous_user_message = ""

        if not self.path.exists():
            self._save({
                "important_memories": [],
                "facts": {},
                "last_updated": None
            })

    def _load(self):
        try:
            return json.loads(self.path.read_text())
        except Exception:
            return {"important_memories": [], "last_updated": None}

    def _save(self, data):
        self.path.write_text(json.dumps(data, indent=2))

    def set_last_user_message(self, text):
        text = (text or "").strip()
        if text:
            if self.last_user_message:
                self.previous_user_message = self.last_user_message
            self.last_user_message = text

    def remember_last(self):
        target = self.previous_user_message or self.last_user_message

        if not target:
            return "I do not have anything recent to remember."

        data = self._load()

        memory = {
            "text": target,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        data["important_memories"].append(memory)
        data["last_updated"] = memory["saved_at"]
        self._save(data)

        return f"I will remember this: {target}"

    def recall_memories(self):
        data = self._load()
        memories = data.get("important_memories", [])

        if not memories:
            return "I do not have any saved memories yet."

        latest = memories[-1]["text"]
        return f"The last important thing I remember is: {latest}"


    def remember_fact(self, key, value):
        data = self._load()
        data.setdefault("facts", {})
        data["facts"][key] = {
            "value": value,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        data["last_updated"] = data["facts"][key]["saved_at"]
        self._save(data)
        return f"I will remember that your {key.replace('_', ' ')} is {value}."

    def recall_fact(self, key):
        data = self._load()
        facts = data.get("facts", {})
        item = facts.get(key)

        if not item:
            return "I do not know that yet."

        return f"Your {key.replace('_', ' ')} is {item['value']}."
