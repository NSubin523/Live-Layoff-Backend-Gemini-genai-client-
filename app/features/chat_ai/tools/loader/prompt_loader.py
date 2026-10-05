from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class PromptLoader:
    """Loads every prompt text file once and serves contents by name.

    Key is the file path relative to prompts/, without extension:
        prompts/intent_system.txt       -> "intent_system"
        prompts/canned/greeting.txt    -> "canned/greeting"
    """

    def __init__(self, prompts_dir: Path = PROMPTS_DIR):
        self._prompts = {}
        for path in prompts_dir.rglob("*.txt"):
            key = path.relative_to(prompts_dir).with_suffix("").as_posix()
            self._prompts[key] = path.read_text(encoding="utf-8").strip()

    def get_loader(self, name: str) -> str:
        try:
            return self._prompts[name]
        except KeyError:
            raise KeyError(f"Prompt '{name}' not found in {PROMPTS_DIR}")


# Single shared instance: prompts load once at startup.
prompt_loader = PromptLoader()