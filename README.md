# Resource Retriever

**Local-first semantic search over a personal library of PDF teaching resources — find the right worksheet by describing it, not by remembering its filename.**

```
$ find-resource find "quadratic word problems year 9"
1. [0.87] C:\Teaching\Year9\Algebra\quadratics_worksheet_v3.pdf — page 2
   "...a ball is thrown upward and its height in metres is modeled by h(t) = -5t^2 + 20t..."
   Open: start "" "C:\Teaching\Year9\Algebra\quadratics_worksheet_v3.pdf"
2. [0.81] https://drive.google.com/file/d/1AbCdEfGhIjKlMnOp/view — page 1
   "...word problems involving projectile motion and quadratic equations..."
   Open: start "" "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOp/view"
Search latency: 42ms
```

## The problem

A working teacher's resource library grows to hundreds or thousands of PDFs scattered across a laptop, a Downloads folder, and Google Drive — exam papers, worksheets, past tests, all with filenames that stopped meaning anything months ago. Finding "that fractions worksheet with the pizza diagram" turns into minutes of manual digging, every single time.

## What it does

`find-resource` is a CLI that indexes a local folder (and, optionally, a Google Drive account) and answers natural-language queries with the right file, the right page, a matching snippet, and a ready-to-run open command — entirely on your machine. No document content ever leaves your computer except when you explicitly authenticate to *read* your own Drive files.

```
find-resource ingest ./teaching_resources   # discover + hash local PDFs
find-resource index                         # extract, chunk, and embed what changed
find-resource index --source drive          # same, for a Google Drive account (read-only)
find-resource find "trig identities test"   # semantic search, ranked results
find-resource drive-login                   # one-time Drive OAuth consent
```

## Architecture

```
ingestion/   →  discover files (local filesystem walk, Drive API listing) and hash/fingerprint them
extraction/  →  pull text per page out of a PDF (PyMuPDF)
chunking/    →  slide a token window over the text using the embedding model's own tokenizer,
                 with exact character offsets and page ranges — never a lossy reconstruction
embedding/   →  turn a chunk of text into a vector (sentence-transformers, CPU-only)
storage/     →  MetadataStore / VectorStore interfaces — SQLite and ChromaDB never leak past them
indexing/    →  the incremental re-index decision engine (a pure, unit-tested function) plus the
                 orchestration that ties discovery → extraction → chunking → embedding together
search/      →  embed a query, rank vector matches, dedupe, join back to file metadata
cli/         →  the Typer command surface (ingest / index / reindex / find / drive-login)
```

Storage is deliberately kept behind two small abstract interfaces (`MetadataStore`, `VectorStore`) so the indexing and search logic never import `sqlite3` or `chromadb` directly — swapping either store later doesn't touch business logic, and both are trivially fakeable in tests.

## Engineering decisions worth calling out

- **Chunking uses the embedding model's own HF tokenizer**, not `tiktoken` — a 500-token `cl100k_base` window is ~550-650 *wordpieces*, and the embedding model silently truncates past 256. Using the model's own tokenizer with `return_offsets_mapping=True` gets exact `(char_start, char_end)` per chunk and guarantees nothing embedded is ever silently cut off. It also avoids a network call to fetch `tiktoken`'s BPE file on first run, which would have quietly broken the tool's "local-only, works offline" promise.
- **The incremental re-index decision logic is a pure function** (`reindex_algorithm.decide_action`) with zero I/O — every NEW / REPROCESS / SKIP / SKIP_BUT_TOUCH / DELETE_STALE branch is unit-tested in isolation, independent of SQLite, Chroma, or the filesystem.
- **A privacy denylist with defense in depth.** Files matching configured folder names, path substrings, or an explicit exclusion list are tracked but never embedded. When a file is excluded *after* already being indexed, its vectors are actively purged from the vector store — and the search layer independently double-checks a file's status before ever returning it, so a stale vector alone can never leak excluded content.
- **Per-file fault isolation.** Indexing ~1,000+ files means something will eventually fail to parse or embed. Every extraction/chunking/embedding/vector-store call is scoped so one corrupt PDF is logged and marked failed — the run continues, it never aborts partway through and silently drops everything after the bad file.
- **Cross-source content dedup.** The same worksheet often lives in Drive, on the laptop, and in Downloads simultaneously. Search results are deduplicated by content hash before ranking, so identical copies never crowd out genuinely different results.
- **Drive integration stays read-only and stateless.** OAuth uses the `drive.readonly` scope only; downloaded bytes live in an in-memory buffer and are never written to disk; the token cache and any client secrets are `.gitignore`d and resolved outside the repo by default.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| CLI | [Typer](https://typer.tiangolo.com/) | Type-hint-driven commands, near-zero boilerplate |
| PDF extraction | [PyMuPDF](https://pymupdf.readthedocs.io/) | Fast, accurate page-level text extraction |
| Embeddings | [sentence-transformers](https://www.sbert.net/) (`all-MiniLM-L6-v2`) | Strong CPU-only baseline for short-passage semantic similarity |
| Vector store | [ChromaDB](https://www.trychroma.com/) | Zero-ops embedded store; metadata filtering built in |
| Metadata store | SQLite | Zero-ops, parameterized queries, trivially portable |
| Drive access | `google-api-python-client` + `google-auth-oauthlib` | Official, read-only, well-documented OAuth flow |
| Tests | pytest + pytest-cov | AAA structure, unit/integration/CLI layers |

## Testing & quality

- **112 tests** across unit, integration, and CLI layers, **96%+ coverage** on touched modules (project floor: 80%).
- Fast unit tests run against fakes/stubs (no real model, no network); a smaller set of integration/CLI tests exercise the real embedding model and a real ChromaDB store end to end.
- Every phase of the build went through a dedicated, independent code-review pass (general correctness + Python-specific idiom/security review) *after* the initial implementation — several real bugs were caught and fixed this way before merge, including:
  - a chunker input that could hang the indexing process indefinitely (unvalidated `overlap_tokens >= window_tokens`),
  - excluded (privacy-denylisted) files that could still surface in search results because their vectors were never purged,
  - an unvalidated CLI flag (`--top-k 0`) that crashed with a raw library traceback instead of a clean error.
- Every fix shipped with a regression test — the review process isn't just "read the code," it's "prove the bug existed, then prove it's gone."

## Project status

| Phase | What | Status |
|---|---|---|
| 1 | Local ingestion, PDF extraction, SQLite metadata | Done |
| 2 | Chunking, embedding, ChromaDB vector store | Done |
| 3 | CLI semantic search end-to-end | Done |
| 4 | Google Drive ingestion (read-only, OAuth) | Done |
| 5 | Incremental re-index at full scale (~1,000+ files), `stats` command | In progress |
| 6 | Test coverage completion (≥80% project-wide, currently 96%+ on touched modules) | In progress |

## Running it locally

```bash
pip install -e ".[dev]"
find-resource ingest /path/to/your/pdfs
find-resource index
find-resource find "whatever you're looking for"

# tests
pytest --cov=resource_retriever --cov-report=term-missing
```

All local state (the SQLite database, the Chroma vector store, any Drive credentials) lives outside the repository by default, under `~/.resource_retriever` — nothing indexed or authenticated ever gets committed.
