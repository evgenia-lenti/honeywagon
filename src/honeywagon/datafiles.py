"""Load the data files that ship with the package."""

import tomllib
from functools import cache
from importlib import resources
from typing import Any


@cache
def load_data(*path: str) -> dict[str, Any]:
    """Read one TOML file from the package's data folder."""
    source = resources.files("honeywagon").joinpath("data", *path)
    return tomllib.loads(source.read_text(encoding="utf-8"))


def load_texts(language: str = "en") -> dict[str, Any]:
    """Read every user-facing text of one language."""
    return load_data("text", f"{language}.toml")
