from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .models import Company
from .sources import REGISTRY

_LIST_KEYS = {
    "title_include", "description_include", "title_exclude", "company_exclude",
    "locations", "location_exclude",
}
_FILTER_KEYS = _LIST_KEYS | {"english_only"}


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Filters:
    title_include: list[str]
    description_include: list[str] = field(default_factory=list)
    title_exclude: list[str] = field(default_factory=list)
    company_exclude: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    location_exclude: list[str] = field(default_factory=list)
    english_only: bool = False


def _read(path) -> dict:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top level must be a mapping")
    return data


def _string_list(data: dict, key: str, path) -> list[str]:
    value = data.get(key) or []
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"{path}: '{key}' must be a list of strings")
    return [v.strip() for v in value if v.strip()]


def load_filters(path) -> Filters:
    data = _read(path)
    unknown = set(data) - _FILTER_KEYS
    if unknown:
        raise ConfigError(f"{path}: unknown key(s) {sorted(unknown)}; expected {sorted(_FILTER_KEYS)}")
    english_only = data.get("english_only", False)
    if not isinstance(english_only, bool):
        raise ConfigError(f"{path}: 'english_only' must be true or false")
    filters = Filters(**{k: _string_list(data, k, path) for k in _LIST_KEYS},
                      english_only=english_only)
    if not (filters.title_include or filters.description_include):
        raise ConfigError(f"{path}: give at least one title_include or description_include term")
    return filters


def load_companies(path) -> list[Company]:
    data = _read(path)
    companies = []
    for i, entry in enumerate(data.get("companies") or []):
        try:
            company = Company(name=entry["name"], ats=entry["ats"], slug=entry["slug"])
        except (KeyError, TypeError):
            raise ConfigError(f"{path}: company #{i + 1} needs name, ats and slug") from None
        if company.ats not in REGISTRY:
            raise ConfigError(
                f"{path}: '{company.name}' uses unsupported ats '{company.ats}'; "
                f"supported: {sorted(REGISTRY)}"
            )
        companies.append(company)
    return companies
