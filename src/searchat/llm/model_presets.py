from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPreset:
    name: str
    url: str
    filename: str


DEFAULT_PRESET_NAME = "qwen2.5-coder-1.5b-instruct-q4_k_m"

# NOTE: URL is pinned to a specific Hugging Face revision (immutable).
PRESETS: dict[str, ModelPreset] = {
    DEFAULT_PRESET_NAME: ModelPreset(
        name=DEFAULT_PRESET_NAME,
        filename="qwen2.5-coder-1.5b-instruct-q4_k_m.gguf",
        url=(
            "https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF/resolve/"
            "f86cb2c1fa58255f8052cc32aeede1b7482d4361/"
            "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
        ),
    ),
}


def get_preset(name: str) -> ModelPreset:
    preset = PRESETS.get(name)
    if preset is None:
        raise ValueError(f"Unknown embedded model preset: {name}")
    return preset
