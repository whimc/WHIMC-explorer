# Versioned releases and deployment

One semantic release version coordinates the plugin, exporter and portal. Every
release supplies two separately named Minecraft builds, also distinguished in their
embedded plugin versions:

- `WHIMC-Explorer-<version>-mc1.21.11.jar` — Java 21 / Paper 1.21.11 target.
- `WHIMC-Explorer-<version>-mc26.x.jar` — Java 25 / currently Paper 26.2 target.
- `WHIMC-Explorer-<version>-web.zip` — cPanel application files, paths relative to app root.
- `WHIMC-Explorer-<version>-source.zip` — source, examples and documentation.
- `SHA256SUMS-<version>.txt` — checksums for these four files.

The `mc26.x` name is a distribution family, not a promise that every 26.x server
version is supported. Check [COMPATIBILITY.md](COMPATIBILITY.md). Install one JAR,
never both. Both variants share the data contract and portal. Independent numeric
version histories are deliberately avoided so paired artifacts stay identifiable.

## Regular workflow

Pushes to main and pull requests run Python, JavaScript and both Java build checks.
Successful builds upload temporary GitHub Actions artifacts. A `vX.Y.Z` tag matching
`VERSION` runs the same checks and publishes a GitHub **prerelease** with permanent
download assets. Releases stay marked pilot/prerelease until live compatibility and
deployment checks justify promoting them. A main-branch push alone does not release
or install anything. Failed tests block release publication.

Use the version helper from the repository root:

```powershell
python tools/version.py patch
# Or: python tools/version.py minor / major
```

It updates `VERSION` and the Maven project version together. Use patch for compatible
fixes, minor for added functionality, major for breaking contracts; document migration
and compatibility changes. It never commits, pushes, tags or deploys on its own.
Commit/review changes, push main, and after its checks pass create a new tag:

```powershell
git tag v0.4.0
git push origin v0.4.0
```

Replace the example tag with the current version. Never move an existing release tag
or overwrite published binaries. Fix a failed release with a new version if its
published assets need changing. Build dependencies are pinned; workflow actions use
verified full commit SHAs, minimal permissions and no production credentials.
The release job alone has repository contents-write permission. GitHub Actions must
be allowed by the organization's policy; no personal token is needed by the workflow.
Dependabot checks Actions, pip and Maven dependencies weekly and proposes PRs; it
does not auto-merge or auto-deploy updates. Review Minecraft API bumps for compatibility.

## cPanel and Minecraft installation

GitHub release publication is automated. Installation remains manual until a separate
cPanel deployment connection and rollback procedure are configured. Download the web
ZIP from the chosen release, back up the private DB, extract/upload into the existing
application root, install that release's requirements if changed, run migrations and
collectstatic, then restart the Python application. Preserve cPanel environment and
Apache configuration. Review release notes before running schema migrations.

For Minecraft, stop the server, replace its Explorer JAR with the matching target
build, preserve config/journal, then restart and check status. A website-only change
does not require a plugin replacement unless its release notes say so.

GitHub publishes versioned downloads; cPanel hosts the private evaluator website.
Automatic production installation, scheduled code changes and unattended version
bumps are not configured. Backups and a compatible schema rollback plan are required
before automating installation; copying old source over a new schema is not a general
rollback mechanism.

References: [GitHub release management](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository),
[GitHub Actions security](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions).
