"""Export the exact skill bundled with this installed framework version."""
from importlib.resources import files
from pathlib import Path

# Every file of the SkillWren-built package; manifest.json pins their exact bytes.
FILES = (("SKILL.md",), ("manifest.json",), ("flows", "dev-loop.md"), ("flows", "enforced.md"),
         ("agents", "openai.yaml"))


def export(destination):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    source = files("chilicrisp").joinpath("skills", "chili-dev")
    for parts in FILES:
        target = destination.joinpath(*parts)
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(source.joinpath(*parts).read_bytes())
    return destination
