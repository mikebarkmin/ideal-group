"""Project configuration save/load functionality."""

import json
from pathlib import Path

from .models import Project


def save_project(project: Project, path: str | Path) -> None:
    """Save project configuration to a JSON file."""
    path = Path(path)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(project.to_dict(), f, indent=2, ensure_ascii=False)


def load_project(path: str | Path) -> Project:
    """Load project configuration from a JSON file."""
    path = Path(path)
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return Project.from_dict(data)
