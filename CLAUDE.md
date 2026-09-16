## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

## Regole Git permanenti

Queste regole valgono per **ogni** sessione, non solo per quella in cui sono state
introdotte. Non vanno reinterpretate né allentate senza un'istruzione esplicita e puntuale
dell'utente.

- **Nessuna pull request**: tutto il lavoro resta su commit locali/nel branch dedicato. Non
  aprire PR verso il branch principale in nessuna circostanza, salvo istruzione esplicita e
  puntuale dell'utente.
- **Nessuna attribuzione a Claude Code**: i commit non devono contenere firme, co-author
  tag, o riferimenti del tipo "Generated with Claude Code" / "Co-Authored-By: Claude" in
  messaggi di commit, PR o codice. I commit vanno attribuiti esclusivamente all'utente/al
  suo identificativo git configurato.

Corollario operativo: prima di modificare qualunque file, creare un branch dedicato
all'intervento. Non lavorare mai direttamente su `main`/`master`.

## Regole per l'avvio dei binari multichain

Queste regole valgono per ogni sessione.

- usare il docker fornito per compilare ed avviare i binari: ./docker nella root del progetto
```bash
./docker/mcsim run mc-build          # compile MultiChain into src/
./docker/mcsim preflight             # can this container do it?

./docker/mcsim shell                 # poke around
```
`./docker/mcsim` supplies an Ubuntu 22.04 userspace with GCC 11 and Boost 1.74.