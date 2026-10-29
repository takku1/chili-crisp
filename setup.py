"""Include the authoritative schemas in wheels without maintaining duplicate sources."""
from pathlib import Path
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py


class BuildWithSchemas(build_py):
    def run(self):
        super().run()
        destination = Path(self.build_lib) / "chilicrisp" / "schemas"
        destination.mkdir(parents=True, exist_ok=True)
        for schema in (Path(__file__).parent / "schemas").glob("*.schema.json"):
            shutil.copyfile(schema, destination / schema.name)


setup(cmdclass={"build_py": BuildWithSchemas})
