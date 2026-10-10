import shutil
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent.parent
output = Path(sys.argv[1]).resolve()
if output == root or root in output.parents:
    raise SystemExit("Choose a staging directory outside the workspace")
output.mkdir(parents=True, exist_ok=True)
core = root / "vox-core"
for name in ["Cargo.toml", "Cargo.lock", "build.rs", "Dockerfile", "Dockerfile.worker"]:
    shutil.copy2(core / name, output / name)
for name in ["src", "services", "migrations", "contracts", "defaults"]:
    destination = output / name
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(core / name, destination)
connections = root / "vox-connections"
for name in ["Cargo.toml", "Cargo.lock"]:
    if (connections / name).exists():
        (output / "vox-connections").mkdir(exist_ok=True)
        shutil.copy2(connections / name, output / "vox-connections" / name)
destination = output / "vox-connections/src"
if destination.exists():
    shutil.rmtree(destination)
shutil.copytree(connections / "src", destination)
print(output)
