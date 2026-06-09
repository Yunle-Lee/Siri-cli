import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from .config import SESSIONS_DIR, ensure_dirs


class Transcript:
    def __init__(self, model_name: str = "system", instructions: str = None):
        self.model_name = model_name
        self.version = "1.1"
        self.entries: list[dict] = []
        if instructions:
            self.entries.append({
                "role": "instructions",
                "id": str(uuid.uuid4()).upper(),
                "contents": [{"type": "text", "text": instructions, "id": str(uuid.uuid4()).upper()}],
                "tool_definitions": []
            })

    def add_user_prompt(self, text: str, images: list[str] = None) -> dict:
        contents = [{"id": str(uuid.uuid4()).upper(), "text": text, "type": "text"}]
        if images:
            for img in images:
                contents.append({"id": str(uuid.uuid4()).upper(), "image_path": img, "type": "image"})
        entry = {
            "options": {},
            "contextOptions": {},
            "contents": contents,
            "id": str(uuid.uuid4()).upper(),
            "role": "user",
        }
        self.entries.append(entry)
        return entry

    def add_response(self, text: str, metadata: dict = None):
        entry = {
            "id": str(uuid.uuid4()).upper(),
            "assets": [],
            "metadata": {
                "systemVersion": "fm-clone 1.0",
                "model": self.model_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **(metadata or {}),
            },
            "contents": [
                {"type": "text", "id": str(uuid.uuid4()).upper(), "text": text}
            ],
            "role": "response",
        }
        self.entries.append(entry)
        return entry

    def get_instructions(self) -> str | None:
        for entry in self.entries:
            if entry["role"] == "instructions" and entry.get("contents"):
                return entry["contents"][0].get("text")
        return None

    def set_instructions(self, text: str | None):
        self.entries = [e for e in self.entries if e["role"] != "instructions"]
        if text:
            self.entries.insert(0, {
                "role": "instructions",
                "id": str(uuid.uuid4()).upper(),
                "contents": [{"type": "text", "text": text, "id": str(uuid.uuid4()).upper()}],
                "tool_definitions": []
            })

    def to_dict(self) -> dict:
        return {
            "transcript": {
                "version": self.version,
                "transcript": {"entries": self.entries},
                "type": "FoundationModels.Transcript"
            },
            "modelName": self.model_name,
        }

    def save(self, name: str = None):
        ensure_dirs()
        if name is None:
            name = str(uuid.uuid4()).upper()
        filepath = SESSIONS_DIR / f"{name}.json"
        filepath.write_text(json.dumps(self.to_dict(), indent=2))
        return filepath

    @classmethod
    def load(cls, path: Path | str) -> "Transcript":
        path = Path(path)
        if not path.suffix:
            path = SESSIONS_DIR / f"{path.name}.json"
        data = json.loads(path.read_text())
        t = cls(model_name=data.get("modelName", "system"))
        t.entries = data["transcript"]["transcript"]["entries"]
        return t

    @classmethod
    def list_sessions(cls) -> list[Path]:
        ensure_dirs()
        return sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    @classmethod
    def latest_session(cls) -> Path | None:
        sessions = cls.list_sessions()
        return sessions[0] if sessions else None

    def get_messages_for_api(self) -> list[dict]:
        messages = []
        instructions = self.get_instructions()
        if instructions:
            messages.append({"role": "system", "content": instructions})
        for entry in self.entries:
            if entry["role"] == "user":
                text_parts = [c["text"] for c in entry.get("contents", []) if c.get("type") == "text"]
                if text_parts:
                    messages.append({"role": "user", "content": "\n".join(text_parts)})
            elif entry["role"] == "response":
                text_parts = [c["text"] for c in entry.get("contents", []) if c.get("type") == "text"]
                if text_parts:
                    messages.append({"role": "assistant", "content": "\n".join(text_parts)})
        return messages
