"""Skill discovery and loading.

Skills are Markdown files in a configurable directory. Each .md file
is one skill — filename (minus extension) is the skill ID. Optional
YAML frontmatter (``---`` delimiters) provides metadata like description.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class SkillMeta:
    name: str
    description: str
    path: Path


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        meta = {}
    body = parts[2].lstrip("\n")
    return meta, body


def discover_skills(skills_dir: Path) -> list[SkillMeta]:
    if not skills_dir.is_dir():
        logger.warning("Skills directory not found: %s", skills_dir)
        return []
    skills: list[SkillMeta] = []
    for md_file in sorted(skills_dir.glob("*.md")):
        name = md_file.stem
        text = md_file.read_text(encoding="utf-8")
        meta, _ = _parse_frontmatter(text)
        description = meta.get("description", name.replace("-", " ").title())
        skills.append(SkillMeta(name=name, description=description, path=md_file))
    return skills


def load_skill_content(skill_name: str, skills_dir: Path) -> str | None:
    path = skills_dir / f"{skill_name}.md"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    _, body = _parse_frontmatter(text)
    return body


def build_skill_prompt(active_skills: list[str], skills_dir: Path) -> str:
    parts: list[str] = []
    for name in active_skills:
        content = load_skill_content(name, skills_dir)
        if content is not None:
            parts.append(f"## Skill: {name}\n\n{content}")
    if not parts:
        return ""
    return "\n\n---\n\n" + "\n\n".join(parts)
