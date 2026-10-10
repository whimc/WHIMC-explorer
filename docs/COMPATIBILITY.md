# Minecraft and runtime compatibility

Explorer provides two separate plugin builds. Install exactly one, with the server
stopped, and remove the previous Explorer JAR before restarting. Preserve its config
and journal directory. Never install both JARs or use `/reload` to switch versions.

| Server target | Explorer JAR suffix | Java bytecode | Verification |
|---|---|---|---|
| Paper 26.2 build 132 | `-mc26.x.jar` | Java 25 | Built/tested; capture verified on the local 26.x pilot |
| Paper 1.21.11 | `-mc1.21.11.jar` | Java 21 | Compiled against 1.21.11 API; journal tests pass; live 1.21.11 integration still required |

The ordinary 26.2 JAR declares API 26.2 and will not load on 1.21.11. The separate
build declares API 1.21.11 and targets Java 21. Paper's runtime guidance lists Java 21
for 1.20–1.21.11 and Java 25 for 26.x:
[Paper getting started](https://docs.papermc.io/paper/getting-started/).

Build from the repository root with Maven and JDK 25 (which can emit Java 21 bytecode):

```powershell
mvn -f plugin/pom.xml package
mvn -f plugin/pom.xml '-Pmc-1.21.11' package
```

Outputs live in `plugin/target-mc26.x/` and `plugin/target-mc1.21.11/`, respectively.
The profile pins Paper `1.21.11-R0.1-20260511.115010-91` and Citizens API
`2.0.41-20260326.063323-24`. The default pins Paper `26.2.build.132-stable` and
Citizens API `2.0.44-20261008.185736-5`. These are compile-time APIs, not bundled
server plugins. Install a Citizens server build explicitly compatible with your
Minecraft version. Explorer uses public Bukkit/Citizens APIs and does not include NMS.

This does not certify Position Tracker, Citizens, Journey, Observations, Science Tools
or the rest of the server pack on 1.21.11. Retain compatible builds of those plugins.
The Python exporter and portal are independent of the Minecraft runtime version;
they require the documented table layouts and bundle contract.

## Required 1.21.11 pilot

Use an isolated 1.21.11 test server with its own compatible worlds; do not downgrade
the existing 26.x worlds in place. Enroll a test UUID, start Explorer capture, and
verify startup/status. Join, walk, click a Citizens NPC, teleport, and quit. Confirm
the journal events and Position Tracker rows, then export and inspect them in the
portal. A successful compile and journal unit tests cannot verify the server event
integration or the other plugins. This runtime pilot has not yet been performed.
