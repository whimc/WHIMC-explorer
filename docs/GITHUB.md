# GitHub repository and release workflow

Use one repository, suggested name **WHIMC-Explorer**, containing the Java plugin, Python exporter/helpers, Django portal, synthetic example, tests and documentation. This keeps data-contract changes coordinated. Position Tracker and the archived Path Generator remain separate repositories.

## Repository

The source repository is [whimc/WHIMC-explorer](https://github.com/whimc/WHIMC-explorer). Clone it with `git clone https://github.com/whimc/WHIMC-explorer.git`. The initial source publication excludes operational records, map artwork and credentials.

Before every commit/push, review staged files for secrets and operational data. The project `.gitignore` excludes `private-data/`, `.venv/`, exported databases, build/release outputs and local configuration. Never force-add them. Roster mappings and map images are stored privately, even though account UUIDs can be resolved publicly. Preserve the original map artwork attribution; select a project license deliberately before describing the repository as open source.

## Build and validate

Requirements: Java 25 + Maven; Python 3.12 with `web/requirements.txt` and `tools/requirements.txt` installed in a virtualenv. From the repository root:

```powershell
mvn -f plugin/pom.xml package
mvn -f plugin/pom.xml '-Pmc-1.21.11' package
$env:EXPLORER_MODE = 'demo'
python web/manage.py test portal
python -m unittest discover -s tools -p 'test_*.py'
python tools/package_release.py
```

The release script includes explicit code/docs and synthetic/example JSON only. It excludes operational rosters, real session exports, secrets, DBs and virtualenvs. Current version is recorded in `VERSION`; tools/docs can change without requiring a new JAR when the Minecraft component is unchanged. Run `package_release.py` after changes to refresh the pilot ZIP and checksums. See [RELEASES.md](RELEASES.md) for automatic tag-based releases, version bumps and distinct Minecraft build names.

For a dependency advisory check, install `pip-audit` in a development environment and run `python -m pip_audit -r web/requirements.txt -r tools/requirements.txt`. Do not treat a clean audit as proof that the application or server configuration is secure.

## Updates

Keep work on reviewable branches and include meaningful validation in pull requests. Run portal/exporter tests for data-contract changes, and plugin tests plus a controlled server session for capture changes. Test cPanel/NetID routing when deployment configuration changes. Publish release artifacts/checksums separately from Git source.

Creating/pushing the repository does not deploy to Minecraft or cPanel. Follow [operations](OPERATIONS.md) for deployments and backups. Automatic production deployment is not configured.
