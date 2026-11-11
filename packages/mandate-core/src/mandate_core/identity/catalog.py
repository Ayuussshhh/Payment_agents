"""Load the shared permission catalog."""

import json
from functools import lru_cache
from pathlib import Path


def catalog_path() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "contracts" / "permissions.json"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("contracts/permissions.json")


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    return json.loads(catalog_path().read_text(encoding="utf-8"))


def expand_roles(roles: list[str]) -> tuple[str, ...]:
    catalog = load_catalog()
    grants: set[str] = set()
    every = [f"{action}:{subject}" for action in catalog["actions"] for subject in catalog["subjects"]]
    known = set(every)
    for role in roles:
        for grant in catalog["roles"][role]:
            if grant == "manage:all":
                grants.update(every)
            elif grant not in known:
                raise KeyError(grant)
            else:
                grants.add(grant)
    return tuple(sorted(grants))
