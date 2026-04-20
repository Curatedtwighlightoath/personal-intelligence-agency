# RAG / Knowledge Base Architecture — Planning Notes

**Status:** Planning. No code yet. This doc captures decisions reached in
conversation so work can resume cleanly in a fresh context.

**Date:** 2026-04-20

---

## 1. Scope

PIA today has three departments: Watchdog (implemented), Marketing
(implemented), R&D (planned). All three are silos — they cannot query each
other's outputs. This is the biggest structural gap and the focus of this
planning round.

Out of scope for this doc (deferred):
- Communications / inbox triage department (secondary — the frontend UI is the
  primary user interface for now).
- Android "PIA on the GO" app (future; flagged where it constrains a decision).

## 2. Future department ideas (brainstormed, not committed)

Ranked rough value-add, for later:

**Tier 1 — highest leverage, clean fit:**
1. Inbox / Comms Triage
2. Research / Librarian (deep, on-demand, multi-hop research — complements
   Watchdog's shallow polling)
3. **Knowledge Base / Memory** ← the subject of this doc

**Tier 2 — strong standalone value:**
4. Finance / Ledger
5. Calendar / Chief of Staff
6. Contract / Legal Reader (diff-vs-prior-version pattern)

**Tier 3 — narrower:**
7. Competitive Intel (specialized Watchdog)
8. Learning / Tutor
9. Analytics / Weekly Digest (probably a Dashboard feature, not a department)

A KB layer is the highest *structural* value-add: without it, every future
department is another silo.

## 3. Atomic Units (AUs) per department

Three AU candidates were considered:

- **Artifact** — whole document (draft post, R&D session log, intel hit).
  Durable, immutable, has authorship. Read-by-ID.
- **Chunk** — embedding-sized slice of an artifact. The retrieval workhorse.
- **Fact / claim** — extracted assertion with provenance
  (e.g. "lib X doesn't support Python 3.14"). First-class, not just a chunk.

**Decision: heterogeneous AUs per department, unified query surface.**

| Department | Primary AU | Rationale |
|---|---|---|
| Watchdog | Chunks | Ingest pipeline, semantic retrieval over hits. No rabbit holes. |
| Marketing | Chunks | Past campaigns + external reference material feed post generation; trend/sentiment is a time-series concern (see §6). |
| R&D | Facts (primary) + Artifacts + Chunks | Session transcripts stored as artifacts and chunked; rabbit-hole knowledge extracted as facts. |

Heterogeneous AUs are a *storage* choice. A single `/api/kb/query` endpoint
federates across them, scoped by department tags. The mistake to avoid is
per-department *databases*.

## 4. Database decision

**Chosen: PostgreSQL + pgvector, single database.**

### Why (summary of the matrix)

Full matrix in conversation log; compressed here.

**Chunks performance:**
- SQLite + sqlite-vec: brute-force only, wall at ~1–5M chunks.
- **pgvector (HNSW): <10ms @ 1M, <30ms @ 10M, sublinear. Iterative-scan
  filtered ANN (0.7+) is the decisive feature.**
- Qdrant/LanceDB: better at extreme scale/filter-selectivity, but adds a
  second store and application-side joins. Unnecessary at PIA scale.
- Graph DB: wrong tool for chunks.

**Facts performance:**
- pgvector alone handles entity lookup, 2-hop relations, and
  vector-similarity on fact summaries. 3+ hop traversal via recursive CTE
  degrades, but facts will be 10–100× fewer than chunks and R&D volume is
  hundreds–low-thousands over the project's lifetime.
- Apache AGE (graph-in-Postgres) was considered and **deferred**: the graph
  perf win kicks in at scales PIA will not reach, and AGE is the least mature
  piece of the stack. It's additive later — same DB, same rows — not a
  migration.
- Neo4j / KuzuDB: real graph perf, but second store, operational overhead,
  cross-store joins to chunks.

**Artifacts:** any DB is fine. Postgres is already there, so put them there.

### Ops wins (real, underrated)

- One `pg_dump`, one backup, one restore path.
- One auth surface, one monitoring integration.
- pgvector is battle-tested; one extension to trust.

### Triggers to revisit (concrete, not vague)

Add AGE (or a graph store beside Postgres) if **any** of these fire:

1. R&D facts exceed ~50K and rabbit-hole queries start appearing in
   slow-query logs.
2. A recursive CTE grows to 4+ hops and the query plan goes quadratic.
3. A real use case for subgraph matching emerges — e.g. "find previous R&D
   sessions whose *pattern* of attempt→failure→pivot matches this one."
   Vector similarity genuinely can't fake this; CTEs can't scale it.

Until one fires, pgvector-only is not a compromise — it's the right tool.

## 5. Schema sketch (illustrative, not final)

Intentionally light. Detailed schema is the next planning step.

### Common envelope

Every AU row carries enough metadata to federate at the query layer:

```
{
  dept: 'watchdog' | 'marketing' | 'rd',
  kind: <AU-specific>,
  ts: timestamptz,
  tags: text[],
  provenance: jsonb,     -- links back to source
  embedding: vector(N),  -- where applicable
}
```

### `artifacts`
Whole-document anchors. Immutable. Referenced by chunks and facts.
- `id`, `dept`, `kind`, `ts`, `title`, `body`, `author`, `tags[]`, `source_url?`

### `chunks`
The retrieval workhorse. HNSW index on embedding. FTS5/`tsvector` for hybrid
BM25. Metadata columns for every filter we'll actually use.
- `id`, `artifact_id` (FK), `dept`, `ts`, `body`, `embedding vector(N)`,
  `tags[]`, `fts tsvector`

### `facts`
Triple/quad-store shape. Indexed parent-pointer for CTE traversal. `jsonb`
only for genuinely variable provenance payload — **not** a schema escape
hatch.
- `id`, `subject_entity_id`, `predicate`, `object_entity_id | object_literal`,
  `confidence`, `outcome` (for R&D: success/abandon/blocked/pending),
  `provenance_artifact_id` (FK), `supersedes_id` (self-FK),
  `embedding vector(N)`, `tags[]`, `ts`

### `entities`
Entity resolution is non-negotiable. Strings-as-entities rot fast.
- `id`, `kind` (repo, product, person, library, concept, …), `canonical_name`,
  `aliases[]`, `tags[]`

## 6. Marketing sentiment / trends

**Not a RAG problem. Don't force it through vector search.**

Episodic time-series table — engagement metrics per published post, pulled on
a schedule. Periodic rollups (daily, weekly, per-platform) drive trend
dashboards. Sentiment scores are derived and stored as a column on the
metrics row, not as facts.

Consider `timescaledb` extension *only if* we hit real time-series
performance pain. Plain Postgres with proper indexes is probably enough.

## 7. Derivation worker

**Decision: worker-time derivation, not write-time or query-time.**

- Departments write raw artifacts.
- A KB worker (APScheduler, in-process like the existing watchdog scheduler)
  picks up new rows, chunks them, embeds, extracts facts where applicable.
- Decouples departments from embedding model choice.
- Makes whole-corpus re-embed tractable when we swap models (which we will).

Embedding model provider follows the same `department_config` pattern already
used for chat/completion providers — vendor-neutral, env-var key refs only.

## 8. Episodic vs. semantic split

Borrowed from cognitive architectures:

- **Episodic layer** — append-only, timestamped events. Marketing engagement
  pulls, R&D session timeline, Watchdog hit history. Cheap, full history.
- **Semantic layer** — derived, periodically rebuilt. Topic summaries,
  entity profiles, current-state-of-product rollups.

Keep them separate. Marketing's sentiment/trend need is episodic. R&D's
rabbit-hole avoidance is semantic. Blurring them hurts both.

## 9. Open questions (to resolve before/during implementation)

1. **Retention policy.** R&D session logs grow fast. Facts forever, raw logs
   expire after N months? Per-dept TTL?
2. **Human-editable KB entries?** Or write-once by departments?
   (Affects UI surface.)
3. **Cross-department writes.** Can Research dept (future) append facts that
   R&D then reads? Probably yes, but need an authorship/trust field on facts.
4. **Android / PIA-on-the-GO sync.** Postgres won't live on the phone. Three
   options, decision deferred until mobile work starts:
   - Server-authoritative (phone is thin HTTP client).
   - SQLite mirror on phone (periodic sync of filtered subset;
     PowerSync/ElectricSQL/hand-rolled delta endpoint).
   - Hybrid (hot subset cached locally, full corpus live).
5. **Embedding model + dimension.** Ties into the derivation worker. Default
   to a 768-dim model for now; worker design must survive dimension changes
   (separate embedding tables per dimension, or re-embed-and-swap).

## 10. Next planning steps (in order)

1. Detailed schema — column types, indexes, constraints, FK cascades.
2. Derivation worker contract — what triggers it, idempotency, failure modes.
3. Query layer API — shape of `/api/kb/query`, filter grammar, hybrid
   ranking strategy.
4. Retention policy per artifact kind.
5. Migration path — the existing `watchdog.db` SQLite has real data. It
   either gets migrated into Postgres or stays as-is and new writes go to
   Postgres with a bridge.

## Appendix: rejected / deferred options

- **SQLite + sqlite-vec for the whole KB.** Scale ceiling too low; loses
  HNSW; single-writer bottleneck once multiple departments write concurrently.
- **Postgres + pgvector + Apache AGE.** Genuinely interesting; deferred. Not
  a v1 requirement. See §4 triggers.
- **Postgres + pgvector + Qdrant.** Overkill at PIA scale. Two stores,
  denormalized payloads, application-side joins.
- **LanceDB + KuzuDB (all embedded).** The "mobile-first" future. Worth a
  second look only if mobile flips from "future" to "primary."
- **Graph DB as primary store.** Wrong tool for chunks; secondary role only.
