# Golden fixtures: the historical `.gml` topologies

Byte-for-byte copies of the five topology files the Shadow campaign ran on,
taken from commit `6278274` before `shadow/` was removed:

| fixture | original |
|---|---|
| `legacy-regional-10n.gml` | `shadow/regionale/topologia_myledger_regionale.gml` |
| `legacy-national-10n.gml` | `shadow/nazionale/topologia_myledger_nazionale.gml` |
| `legacy-continental-10n.gml` | `shadow/continentale/topologia_myledger_continentale.gml` |
| `legacy-intercontinental-10n.gml` | `shadow/intercontinentale/topologia_myledger_intercontinentale.gml` |
| `legacy-global-10n.gml` | `shadow/config/topologies/intercontinental-global-10n.gml` |

`test_legacy_topologies.py` asserts that exporting the migrated
`configs/topologies/legacy-*.yaml` reproduces each of these **exactly**. That
is the proof the migration was lossless, and it is why these files are kept
rather than described: a description of a topology can be wrong, a byte
comparison cannot.

If a change to the latency model or the exporter is intended, these fixtures
must be regenerated *deliberately* and the change explained in
`docs/migration-from-shadow.md` — silently updating them would discard the
only evidence that new runs are comparable with the archived campaign.
