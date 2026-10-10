"""Package explicit source trees only; private data/config and environments are excluded."""
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "dist"
DEST.mkdir(exist_ok=True)
JAR = ROOT / "plugin/target/WHIMC-Explorer-0.3.0.jar"
LEGACY_JAR = ROOT / "plugin/target-mc1.21.11/WHIMC-Explorer-0.3.0-mc1.21.11.jar"
if not all(p.is_file() for p in (JAR, LEGACY_JAR)):
    raise SystemExit("Build the default and mc-1.21.11 Maven profiles first")
files = [ROOT / "README.md", ROOT / "CPANEL-SETUP.md", ROOT / ".gitignore", ROOT / "plugin/pom.xml"]
for folder in ("web", "tools", "deploy", "plugin/src", "docs"):
    for path in (ROOT / folder).rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts and "static-built" not in path.parts:
            if path.suffix == ".json" and path.relative_to(ROOT).as_posix() not in {"web/demo.json", "tools/catalog.example.json", "tools/export-config.example.json"}:
                continue
            if path.suffix in {".py", ".json", ".txt", ".md", ".html", ".css", ".js", ".java", ".yml"} or path.name == ".htaccess.example":
                files.append(path)
archive = DEST / "WHIMC-Explorer-0.3.0-pilot.zip"
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
    for path in sorted(files):
        bundle.write(path, path.relative_to(ROOT).as_posix())
    bundle.write(JAR, JAR.name)
    bundle.write(LEGACY_JAR, LEGACY_JAR.name)
jar_copy = DEST / JAR.name
jar_copy.write_bytes(JAR.read_bytes())
legacy_copy = DEST / LEGACY_JAR.name
legacy_copy.write_bytes(LEGACY_JAR.read_bytes())
manifest = "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in (archive, jar_copy, legacy_copy))
(DEST / "SHA256SUMS.txt").write_text(manifest, encoding="ascii")
print(f"Packaged {len(files)} source files and plugin into {archive}")
