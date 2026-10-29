"""One schema provider for source checkouts, installed wheels and zip imports."""
from functools import lru_cache
from importlib.resources import files
import json

from jsonschema import Draft202012Validator


@lru_cache(maxsize=10)
def _validator(name):
    if name not in {"experiment", "result", "project", "comparison", "field-oracle", "ocean-oracle",
                    "development", "research", "acceptance-policy", "acceptance-receipt"}:
        raise ValueError(f"unknown schema: {name}")
    resource = files("chilicrisp").joinpath("schemas", f"{name}.schema.json")
    schema = json.loads(resource.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate(value, name):
    _validator(name).validate(value)
