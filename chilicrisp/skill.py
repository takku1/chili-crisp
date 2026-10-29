"""Export the exact skill bundled with this installed framework version."""
from importlib.resources import files
from pathlib import Path


def export(destination):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    source = files("chilicrisp").joinpath("skills", "chili-dev")
    for parts in (("SKILL.md",), ("agents", "openai.yaml")):
        target = destination.joinpath(*parts)
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(source.joinpath(*parts).read_bytes())
    return destination
