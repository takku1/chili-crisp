"""Validate the built wheel's schemas outside the source tree, without installing it."""
from pathlib import Path
import subprocess
import sys
import zipfile

root = Path(__file__).resolve().parents[1]
wheels = list((root / "dist").glob("chilicrisp-*.whl"))
if len(wheels) != 1:
    raise SystemExit("Expected exactly one Chili Crisp wheel in dist/")
with zipfile.ZipFile(wheels[0]) as archive:
    schemas = [name for name in archive.namelist() if name.startswith("chilicrisp/schemas/")]
    if len(schemas) != 4:
        raise SystemExit(f"Wheel must contain all four schemas: {schemas}")
# zipimport loads code from the wheel; JSON schemas need extraction because the
# runner's contract also hashes real comparator files on disk.
import shutil
import uuid
directory = root / ("test-artifacts-" + uuid.uuid4().hex)
directory.mkdir()
try:
    with zipfile.ZipFile(wheels[0]) as archive:
        archive.extractall(directory)
    script = """
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from chilicrisp.runner import validate
import chilicrisp.runner as runner
assert Path(runner.__file__).is_relative_to(Path(sys.argv[1]))
validate(json.loads(Path(sys.argv[2]).read_text()), 'experiment')
print('Installed wheel schema validation passed')
"""
    subprocess.run([sys.executable, "-P", "-c", script, str(directory),
                    str(root / "examples/experiment.json")], cwd=directory, check=True)
finally:
    shutil.rmtree(directory)
