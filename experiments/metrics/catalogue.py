"""The authoritative catalogue of every metric the harness produces.

One place says, for each table and each column: what it means, where the
number comes from, and whether it is **observed** (read directly from a node
or the kernel), **derived** (computed from observed values by a documented
formula) or **unavailable** (declared absent, with the reason).

That third state is the reason this file exists. A metric that stopped being
measurable when Shadow was replaced must not quietly become an empty column;
it must say so, and say why. ``metrics_schema_report.md`` is generated from
here, so the documentation cannot drift from the code.
"""

from __future__ import annotations

from dataclasses import dataclass, field

OBSERVED = "observed"
DERIVED = "derived"
UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class Column:
    name: str
    status: str
    description: str
    source: str = ""
    unit: str = ""
    note: str = ""


@dataclass(frozen=True)
class Table:
    name: str
    description: str
    produced_by: str
    #: A historical table, produced by the migrated campaign analyser.
    historical: bool = False
    columns: list = field(default_factory=list)

    @property
    def enforced(self) -> bool:
        """Whether the validator may fail a run over this table's header.

        Only the tables THIS harness writes. The historical ones come from
        migrated code whose writer emits the union of the keys the data
        actually produced, so their header legitimately narrows when a run has
        no sortition lines or no recomputed chi-square. Their real contract is
        the archive, and tests/golden/test_csv_contract.py holds them to it.
        Enforcing a fixed list here would fail honest runs and teach everyone
        to ignore the validator.
        """
        return not self.historical

    @property
    def column_names(self) -> list:
        return [column.name for column in self.columns]


# ---------------------------------------------------------------------------
# Historical tables. Column names are those of the archived Shadow campaign
# and must not change: every report and every comparison keys on them.
# ---------------------------------------------------------------------------

HISTORICAL_TABLES = [
    Table("run_index", "One row per run: the sealed configuration and the extraction verdict.",
          "analysis.legacy.analizza_esperimenti", historical=True, columns=[
              Column("run_id", OBSERVED, "Run identifier.", "the run directory name"),
              Column("livello", OBSERVED, "Geographic scenario.",
                     "manifest.scenario (native) or the level directory (legacy)"),
              Column("tbt", OBSERVED, "target-block-time.", "params.dat", "s"),
              Column("path", OBSERVED, "Absolute path of the run on the machine that analysed it.",
                     "the filesystem",
                     note="Machine-specific by construction; it is provenance, not data."),
          ]),
    Table("block_times", "Inter-block interval inside the wPoA window against the target.",
          "analysis.legacy.analizza_esperimenti", historical=True, columns=[
              Column("blocchi_misurati", DERIVED, "Blocks in the measurement window.",
                     "listblocks, minus setup-first-blocks"),
              Column("dt_medio_s", DERIVED, "Mean interval.",
                     "differences of the block header timestamps", "s"),
              Column("dt_sd_s", DERIVED, "Standard deviation of the interval.", "same", "s"),
              Column("scarto_pct", DERIVED, "Relative gap against target-block-time.",
                     "(mean - target)/target", "%"),
          ]),
    Table("proposers", "Observed block share per miner against its published weight.",
          "analysis.legacy.analizza_esperimenti", historical=True, columns=[
              Column("blocchi", OBSERVED, "Blocks proposed.", "listblocks, miner field"),
              Column("quota_osservata", DERIVED, "Observed share.", "blocks / total"),
              Column("peso_ultimo", OBSERVED, "Last published weight.", "wpoa-weights stream"),
              Column("quota_attesa", DERIVED, "Expected share.", "w_i / W_tot"),
              Column("delay_medio_s", OBSERVED, "Mean sortition delay.",
                     "debug.log, wPoA-sortition lines", "s"),
          ]),
    Table("chisq", "Chi-square of the proposer distribution against the weights.",
          "analysis.legacy.analizza_esperimenti", historical=True, columns=[
              Column("chi2_ricalcolato", DERIVED, "Recomputed statistic.",
                     "observed vs expected counts"),
              Column("p_value", DERIVED, "p-value.", "scipy.stats.chi2.sf",
                     note="Declared missing, never estimated, when scipy is absent."),
              Column("campione_sufficiente", DERIVED,
                     "Whether the minimum expected count reaches 5.", "min expected >= 5"),
          ]),
    Table("epoch_shares", "Per-epoch block share against the weight in force in that epoch.",
          "analysis.legacy.analizza_esperimenti", historical=True, columns=[
              Column("epoca", DERIVED, "Epoch index.", "height // weight-epoch-length"),
              Column("peso_epoca", OBSERVED, "Weight readable at the chain tip then.",
                     "wpoa-weights"),
          ]),
    Table("weights_trajectory", "Published weight per host and epoch.",
          "analysis.legacy.analizza_esperimenti", historical=True, columns=[
              Column("peso", OBSERVED, "Published integer weight.", "wpoa-weights payload"),
              Column("height", OBSERVED, "Confirmation height of the record.", "stream item"),
          ]),
    Table("sortition_margins", "Timer-race margin G, the Prop. 5.18 regime indicator.",
          "analysis.legacy.analizza_esperimenti", historical=True, columns=[
              Column("G_medio_s", DERIVED, "Mean gap between the two best delays.",
                     "debug.log sortition scores", "s"),
              Column("frazione_G_sotto_100ms", DERIVED,
                     "Fraction of rounds whose margin is under 100 ms.", "same"),
              Column("rtt_max_ms", DERIVED, "Worst end-to-end RTT of the topology.",
                     "shortest path over the .gml", "ms"),
          ]),
    Table("alternanze", "Consecutive blocks by the same proposer, observed against expected.",
          "analysis.legacy.analizza_esperimenti", historical=True, columns=[
              Column("consecutivi_osservati", OBSERVED, "Observed runs of length >= 2.",
                     "listblocks"),
              Column("consecutivi_attesi", DERIVED, "Expected from the weight shares.",
                     "sum of squared shares"),
          ]),
    Table("forks", "Chain consistency across nodes at the end of the run.",
          "analysis.legacy.analizza_esperimenti", historical=True, columns=[
              Column("teste_distinte", OBSERVED, "Distinct best hashes.", "node_state.csv"),
              Column("hash_sepolti_distinti", OBSERVED,
                     "Distinct hashes at a common buried height.", "node_state.csv"),
          ]),
    Table("verify", "Independent recomputation of the published weights.",
          "analysis.legacy.analizza_esperimenti", historical=True, columns=[
              Column("verificato", OBSERVED, "Whether the node verified the epoch.",
                     "weightverifyweights"),
              Column("non_validi", OBSERVED, "Records that failed verification.", "same"),
          ]),
    Table("esg", "Certified ESG score per host.", "analysis.legacy.analizza_esperimenti",
          historical=True, columns=[
              Column("esg", OBSERVED, "Certified score.", "weight-engine-esg stream"),
          ]),
    Table("gas", "GAS economy: distribution, refills, reconciliation, treasury.",
          "analysis.legacy.analizza_esperimenti", historical=True, columns=[
              Column("gas_riconciliato_totale", OBSERVED, "Total returned to the treasury.",
                     "reconciliation.csv", "GAS"),
              Column("saldo_treasury", OBSERVED, "Final treasury balance.",
                     "getaddressbalances", "GAS"),
          ]),
]


# ---------------------------------------------------------------------------
# New tables. Real execution makes a time series possible where the simulator
# only allowed a final snapshot.
# ---------------------------------------------------------------------------

NATIVE_TABLES = [
    Table("node_observations",
          "Per-node RPC sample, one row per node per tick. The time series the "
          "Shadow suite could not take, because sampling inside the simulation "
          "cost simulated time.",
          "runtime.collectors.rpc", columns=[
              # The order below is the file's order, which is
              # runtime.collectors.rpc.OBSERVATION_COLUMNS. Readers index by
              # position, so the catalogue tracks the writer, not the reverse.
              Column("run_id", OBSERVED, "Run identifier.", "the manifest"),
              Column("scenario", OBSERVED, "Scenario label.", "the manifest"),
              Column("seed", OBSERVED, "Master seed.", "the manifest"),
              Column("node_id", OBSERVED, "Node name.", "the plan"),
              Column("role", OBSERVED, "miner | company | admin | ca.", "the plan"),
              Column("organization", OBSERVED, "Owning organisation.", "the plan"),
              Column("geographic_scope", OBSERVED,
                     "regional | national | continental | intercontinental.", "the plan"),
              Column("region", OBSERVED, "Region of the node's location.", "the topology"),
              Column("country", OBSERVED, "Country.", "the topology"),
              Column("continent", OBSERVED, "Continent.", "the topology"),
              Column("timestamp_wallclock", OBSERVED, "UTC time of the sample.",
                     "the host clock", "ISO-8601",
                     note="Comparable across machines. NOT comparable with the Shadow "
                          "campaign's simulated time; see docs/metrics.md."),
              Column("timestamp_monotonic", OBSERVED,
                     "Monotonic clock, the only one safe for differences.",
                     "time.monotonic", "s",
                     note="Does not jump when the host clock is adjusted."),
              Column("block_height", OBSERVED, "Chain height at this node.", "getinfo.blocks"),
              Column("block_hash", OBSERVED, "Best block hash.", "getbestblockhash"),
              Column("previous_block_hash", OBSERVED, "Parent of the best block.", "getblock"),
              Column("block_time", OBSERVED, "Header timestamp of the best block.",
                     "getblock.time", "unix s"),
              Column("peer_count", OBSERVED, "Connected peers.", "getinfo.connections"),
              Column("peer_connectivity", DERIVED, "1 when the node has any peer.",
                     "peer_count > 0"),
              Column("transaction_count", OBSERVED, "Transactions in the best block.",
                     "getblock.tx"),
              Column("confirmed_transaction_count", UNAVAILABLE,
                     "Chain-wide confirmed transaction total.",
                     note="MultiChain exposes no chain-wide counter; summing it would "
                          "mean walking every block on every tick. Left empty rather "
                          "than filled with a partial count."),
              Column("mempool_size", OBSERVED, "Unconfirmed transactions.", "getmempoolinfo"),
              Column("sync_lag", DERIVED, "Blocks behind the highest node in this sample.",
                     "max(height) - height", "blocks"),
              Column("rpc_errors", OBSERVED, "Cumulative RPC failures for this node.",
                     "the collector's own counter"),
              Column("p2p_errors", UNAVAILABLE, "Cumulative P2P errors.",
                     note="Not exposed over RPC. Recoverable from debug.log after the "
                          "run; the column exists so a later extractor can fill it "
                          "without a schema change."),
              Column("reachable", OBSERVED, "Whether the node answered this tick.",
                     "the collector"),
          ]),
    Table("block_sightings",
          "First time each node reported each block hash. Differences across "
          "nodes are the propagation time.",
          "runtime.collectors.rpc", columns=[
              Column("first_seen_wallclock", OBSERVED, "First sighting, UTC.",
                     "the collector", "ISO-8601"),
              Column("first_seen_monotonic", OBSERVED, "First sighting, monotonic.",
                     "the collector", "s"),
          ]),
    Table("block_propagation",
          "Per block: how long it took to reach every node that saw it.",
          "metrics.extractors.extract_propagation", columns=[
              Column("block_height", DERIVED, "Height of the block.", "block_sightings"),
              Column("block_hash", OBSERVED, "Block hash.", "block_sightings"),
              Column("nodes_seen", DERIVED, "Nodes that reported this hash.",
                     "block_sightings"),
              Column("first_seen_monotonic", OBSERVED, "Earliest sighting.",
                     "block_sightings", "s"),
              Column("last_seen_monotonic", OBSERVED, "Latest sighting.",
                     "block_sightings", "s"),
              Column("propagation_time", DERIVED,
                     "Last sighting minus first, across nodes.",
                     "last_seen_monotonic - first_seen_monotonic", "s",
                     note="Resolution is the sampling interval, so it is an upper "
                          "bound rather than a wire-level measurement."),
          ]),
    Table("process_samples", "CPU, memory and disk of every process the harness started.",
          "runtime.collectors.process", columns=[
              Column("cpu_seconds_total", OBSERVED, "Cumulative CPU time.",
                     "/proc/<pid>/stat", "s"),
              Column("cpu_percent", DERIVED, "CPU over the interval since the last sample.",
                     "/proc/<pid>/stat utime+stime", "%"),
              Column("memory_bytes", OBSERVED, "Resident set size.",
                     "/proc/<pid>/status VmRSS", "B"),
              Column("disk_read_bytes", OBSERVED, "Bytes read from disk.",
                     "/proc/<pid>/io", "B",
                     note="Empty, not zero, when unreadable - which is the normal case "
                          "for a process started through sudo."),
              Column("disk_write_bytes", OBSERVED, "Bytes written to disk.",
                     "/proc/<pid>/io", "B"),
              Column("process_restarts", OBSERVED, "Times the harness restarted it.",
                     "the process registry"),
          ]),
    Table("netem_conditions",
          "The impairment actually installed, per link and direction.",
          "metrics.extractors.netem", columns=[
              Column("netem_delay_ms", OBSERVED, "Configured one-way delay.",
                     "topology-realized.json", "ms"),
              Column("netem_jitter_ms", OBSERVED, "Configured jitter.",
                     "topology-realized.json", "ms",
                     note="New. The Shadow campaign carried jitter 0 everywhere, "
                          "because the field was never implemented "
                          "(shadow/shadow#3601)."),
              Column("netem_loss_percent", OBSERVED, "Configured loss.",
                     "topology-realized.json", "%"),
              Column("netem_bandwidth_mbps", OBSERVED, "Configured rate.",
                     "topology-realized.json", "Mbit/s"),
              Column("measured_delay_ms", UNAVAILABLE, "Delay measured on the wire.",
                     note="Would need a probe on every link, whose own traffic would "
                          "perturb the run. Configured values are reported as "
                          "configured, never as measured."),
          ]),
    Table("explorer_blocks",
          "One row per block, collected by polling the admin as a block "
          "explorer. Gap-free: every intermediate height is walked.",
          "runtime.collectors.rpc_explorer", columns=[
              Column("height", OBSERVED, "Block height.", "getblockhash walk"),
              Column("hash", OBSERVED, "Block hash.", "getblock"),
              Column("previous_block_hash", OBSERVED, "Parent hash.", "getblock"),
              Column("block_time", OBSERVED, "Header timestamp.", "getblock", "unix s"),
              Column("observed_wallclock", OBSERVED, "When the explorer saw it.",
                     "the collector", "ISO-8601",
                     note="Bounded by the polling interval: an upper bound on "
                          "when the block appeared, not when it was produced."),
              Column("miner", OBSERVED, "Proposer address.", "getblock.miner"),
              Column("miner_host", DERIVED, "Proposer host name.",
                     "runtime/shared/*.addr"),
              Column("proposer_weight", OBSERVED,
                     "The proposer's weight in the registry at that moment.",
                     "getallweights",
                     note="Empty for a node with no weight - the admin during "
                          "the setup phase - which is correct, not missing."),
              Column("total_weight", OBSERVED, "Sum of all weights then.",
                     "getallweights"),
              Column("size_bytes", OBSERVED, "Block size.", "getblock.size", "B"),
              Column("transaction_count", OBSERVED, "Transactions in the block.",
                     "getblock.tx"),
              Column("gap_filled", DERIVED,
                     "1 when the block was recovered by walking a gap rather "
                     "than seen at the tip.", "the collector"),
          ]),
    Table("explorer_transactions", "One row per transaction of every block.",
          "runtime.collectors.rpc_explorer", columns=[
              Column("txid", OBSERVED, "Transaction id.", "getblock.tx"),
              Column("index_in_block", OBSERVED, "Position in the block.", "getblock.tx"),
              Column("size_bytes", OBSERVED, "Transaction size.", "getblock", "B",
                     note="Empty when the build returns tx as bare txids."),
              Column("fee", OBSERVED, "Fee paid.", "getblock", "GAS",
                     note="Empty unless the node returns the verbose form."),
              Column("kind", DERIVED, "coinbase or tx.", "position and vin"),
              Column("from_address", UNAVAILABLE, "Sender.",
                     note="Resolving it needs the previous output of every input, "
                          "one RPC per input per transaction. Left empty rather "
                          "than filled from the wallet, which only knows its own."),
          ]),
    Table("explorer_chain_state",
          "Every node's own view, every tick: the half a single explorer "
          "cannot provide.",
          "runtime.collectors.rpc_explorer", columns=[
              Column("node_id", OBSERVED, "The node reporting.", "the plan"),
              Column("block_height", OBSERVED, "Its own height.", "getinfo.blocks"),
              Column("best_hash", OBSERVED, "Its own tip.", "getbestblockhash"),
              Column("peer_count", OBSERVED, "Its peers.", "getinfo.connections"),
              Column("mempool_size", OBSERVED, "Its unconfirmed pool.",
                     "getmempoolinfo"),
              Column("reachable", OBSERVED, "Whether it answered.", "the collector"),
          ]),
    Table("fork_events", "Divergence between nodes, observed over time.",
          "metrics.extractors.forks", columns=[
              Column("fork_detected", DERIVED, "1 when nodes disagree at a buried height.",
                     "node_observations across nodes"),
              Column("fork_depth", DERIVED, "Heights over which the disagreement persists.",
                     "same", "blocks",
                     note="Bounded below by the sampling interval: a fork that heals "
                          "between two ticks is invisible. The epoch sampler's "
                          "node_state_epochs.csv covers the coarser case."),
          ]),
]

ALL_TABLES = HISTORICAL_TABLES + NATIVE_TABLES


def table(name: str) -> Table:
    for entry in ALL_TABLES:
        if entry.name == name:
            return entry
    raise KeyError(name)


def status_counts() -> dict:
    counts = {OBSERVED: 0, DERIVED: 0, UNAVAILABLE: 0}
    for entry in ALL_TABLES:
        for column in entry.columns:
            counts[column.status] = counts.get(column.status, 0) + 1
    return counts


def as_dict() -> dict:
    return {
        "tables": [
            {
                "name": entry.name,
                "description": entry.description,
                "produced_by": entry.produced_by,
                "historical": entry.historical,
                "columns": [
                    {"name": c.name, "status": c.status, "description": c.description,
                     "source": c.source, "unit": c.unit, "note": c.note}
                    for c in entry.columns
                ],
            }
            for entry in ALL_TABLES
        ],
        "status_counts": status_counts(),
    }
