# resurge — Drop-in replacement for Python `backoff`

## Target Library

**Package:** [backoff](https://pypi.org/project/backoff/) (by litl/bgreen-litl)
**Downloads:** 130.8M/month (32.3M/week)
**Status:** Archived August 8, 2025 — no releases since October 2022, 43 open issues, 21 open PRs
**Maintainers:** 1 (bgreen-litl) — inactive
**Stars:** 2,698
**Why replace:** Officially archived with no maintenance path. 130M+ monthly downloads with zero security updates. `tenacity` (261M/mo) exists but has a completely different API — not a drop-in replacement. No maintained package replicates backoff's decorator API.

## Project Scope

Drop-in replacement for `backoff` with identical public API. Users change only the import (`import resurge as backoff` or `from resurge import on_exception, on_predicate`).

### Public API (9 exports, matches backoff exactly)

**Decorators:**
- `on_exception(wait_gen, exception, *, max_tries, max_time, jitter, giveup, on_success, on_backoff, on_giveup, raise_on_giveup, logger, backoff_log_level, giveup_log_level)` — retry on exception
- `on_predicate(wait_gen, predicate, *, max_tries, max_time, jitter, on_success, on_backoff, on_giveup, logger, backoff_log_level, giveup_log_level)` — retry on predicate

**Wait generators:**
- `expo(base=2, factor=1, max_value=None)` — exponential backoff
- `fibo(max_value=None)` — Fibonacci sequence
- `constant(interval=1)` — fixed interval (also accepts iterable)
- `runtime` — derive wait from return value/exception

**Jitter functions:**
- `full_jitter` — AWS-style full jitter (default)
- `random_jitter` — add up to 1s random jitter

### Compatibility layer

`resurge.compat.backoff` module: allows `import resurge.compat.backoff as backoff` for zero-change migration.

## Architecture

```
resurge/
├── __init__.py          # public API exports
├── _decorator.py        # on_exception, on_predicate decorator factory
├── _sync.py             # sync retry loop
├── _async.py            # async retry loop (transparent async support)
├── _wait_gen.py         # expo, fibo, constant, runtime generators
├── _jitter.py           # full_jitter, random_jitter
├── _types.py            # type definitions, protocols
├── compat/
│   ├── __init__.py
│   └── backoff.py       # compatibility shim (re-exports everything)
├── py.typed             # PEP 561 marker
└── _version.py          # version
```

## Key Design Decisions

- **Zero dependencies** — pure Python
- **Transparent async support** — same decorators work on sync and async functions (inspect-based detection, like original backoff)
- **Type-annotated** — full type stubs, PEP 561 compliant, `py.typed` marker
- **Python >=3.9** — drop Python 2/3.7/3.8 support, use modern typing
- **100% API compatible** — all parameter names, defaults, and behaviors match backoff 2.2.1
- **Event handlers** — `on_success`, `on_backoff`, `on_giveup` callbacks with same signature (dict with `target`, `args`, `kwargs`, `tries`, `elapsed`, `wait`, `value`/`exception`)

## Deliverables

- PyPI package: `resurge`
- GitHub repo: `agentine/resurge`
- Full test suite with pytest (sync + async coverage)
- Compatibility verified against backoff's own test suite patterns

## Phases

### Phase 1: Project setup + core decorators
- Project scaffold (pyproject.toml, CI, linting)
- `_wait_gen.py`: expo, fibo, constant, runtime
- `_jitter.py`: full_jitter, random_jitter
- `_sync.py`: sync retry loop
- `_decorator.py`: on_exception, on_predicate (sync only)
- Basic tests

### Phase 2: Async support + event handlers
- `_async.py`: async retry loop
- Transparent async detection in decorators
- Event handler callbacks (on_success, on_backoff, on_giveup)
- Async event handler support
- Logging integration

### Phase 3: Types + compatibility + edge cases
- Full type annotations with generics
- `py.typed` marker
- `resurge.compat.backoff` compatibility module
- Edge cases: max_tries=1, max_time=0, generator exhaustion, nested decorators

### Phase 4: Testing + docs + release
- Comprehensive test suite (sync, async, edge cases, logging)
- README with migration guide
- API documentation
- PyPI publish preparation
- GitHub repo setup + CI
