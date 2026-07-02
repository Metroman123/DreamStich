import json
from pathlib import Path


class DreamAIDirector:
    def __init__(self):
        self.model = None
        self.model_path = self.find_model()
        self.status = "AI unavailable. Using Python rules."

        if self.model_path:
            self.load_model()

    def build_dream_arc(self, mood_words):
        if self.last_ai_result and self.last_ai_result.get("arc"):
            return self.last_ai_result.get("arc")

        mood_text = self.mood_entry.get().strip().lower() if hasattr(self, "mood_entry") else ""
        ai_result = self.get_ai_dream_direction(mood_text, mood_words)
        return ai_result.get("arc", self.build_dream_arc_rules(mood_words))

    def find_model(self):
        search_dirs = [
            Path("ai"),
            Path("models"),
            Path("model"),
            Path("."),
        ]

        for folder in search_dirs:
            if folder.exists():
                ggufs = list(folder.glob("*.gguf"))
                if ggufs:
                    return ggufs[0]

        return None

    def load_model(self):
        try:
            from llama_cpp import Llama

            self.model = Llama(
                model_path=str(self.model_path),
                n_ctx=2048,
                n_threads=6,
                verbose=False,
            )
            self.status = f"Local AI loaded: {self.model_path.name}"
        except Exception as e:
            self.model = None
            self.status = f"AI failed to load. Using Python rules. Reason: {e}"

    def available(self):
        return self.model is not None

    def analyze_mood(self, mood_text, fallback_tags, fallback_arc):
        if not self.available() or not mood_text.strip():
            return {
                "tags": fallback_tags,
                "arc": fallback_arc,
                "source": "python_rules",
                "summary": "Using built-in Python dream rules.",
            }

        prompt = f"""
You are the DreamStitch AI Director.

The user gave this mood or experience:
"{mood_text}"

Return ONLY valid JSON.

Use this format:
{{
  "tags": ["liminal", "surreal", "vhs"],
  "arc": ["liminal", "surreal", "vhs", "night", "jazz", "unknown"],
  "summary": "short explanation"
}}

Allowed arc categories:
liminal, surreal, vhs, night, jazz, nature, tech, ytp, unknown

Keep tags short. No paragraphs.
"""

        try:
            result = self.model(
                prompt,
                max_tokens=220,
                temperature=0.45,
                stop=["</s>"],
            )

            text = result["choices"][0]["text"].strip()

            start = text.find("{")
            end = text.rfind("}") + 1

            if start == -1 or end == 0:
                raise ValueError("No JSON found in AI response.")

            data = json.loads(text[start:end])

            tags = data.get("tags", fallback_tags)
            arc = data.get("arc", fallback_arc)
            summary = data.get("summary", "AI generated dream direction.")

            tags = [str(t).lower().strip() for t in tags if str(t).strip()]
            arc = [str(a).lower().strip() for a in arc if str(a).strip()]

            if not tags:
                tags = fallback_tags

            if not arc:
                arc = fallback_arc

            return {
                "tags": tags,
                "arc": arc,
                "source": "local_ai",
                "summary": summary,
            }

        except Exception as e:
            return {
                "tags": fallback_tags,
                "arc": fallback_arc,
                "source": "python_rules",
                "summary": f"AI director failed. Using Python rules. Reason: {e}",
            }