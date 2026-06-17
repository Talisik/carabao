---
name: carabao
description: >-
  Use when building, running, or debugging an app that uses the carabao Python
  framework OR its underlying lane2lane (l2l) pipeline engine. Triggers: the
  `moo` CLI (moo dev / run / init / new); the `carabao` package (Core, Settings,
  Form, F, Field, db hubs mongo/redis/es/pg/amongo/aredis); imports from `l2l`
  (Lane, AsyncLane, Mock, TerminateKind, events, logger); a class with a
  `process(self, value)` method or a `lanes = {priority: ...}` map; a
  `primary()` classmethod; `Lane.start(...)`; lane modules under a
  LANE_DIRECTORIES path; or a carabao.cfg file. carabao builds pub/sub pipelines
  on top of lane2lane — this skill covers both layers.
---

# carabao + lane2lane

Two layers, one skill:

- **lane2lane (`l2l`)** — the pipeline engine. You define **lanes** (units that
  transform/act on data) and wire them with integer priorities. Pure library.
- **carabao** — a framework *on top of* lane2lane. Adds the `moo` CLI, a settings
  system, env-file handling, database hubs, and an interactive dev UI.

If a project imports only `l2l`, just the lane2lane part applies. If it has a
`carabao.cfg` / `moo` / `carabao` package, both apply.

---

# Part 1 — lane2lane (`l2l`): the pipeline

## Defining a lane

Subclass `Lane`, implement `process(self, value)`. May return a value or
`yield` items downstream (generator):

```python
from l2l import Lane

class MyLane(Lane):
    def process(self, value):
        yield f"{value} - processed"
```

## Primary lanes (entry points)

Only **primary** lanes are runnable via `Lane.start(...)`. Override `primary()`:

```python
class Main(Lane):
    @classmethod
    def primary(cls) -> bool:
        return True

    def process(self, value):
        yield transform(value)
```

## Lane ordering — the `lanes` map

Declare lanes to run before/after via a `{priority: lane}` dict. **Negative =
before this lane, positive = after.** More-negative runs earliest; higher-positive
runs latest. Values: a class, a string name, or `None` (removes a lane set at
that priority).

```python
class Main(Lane):
    @classmethod
    def primary(cls) -> bool:
        return True

    lanes = {
        -10: "PreprocessLane",  # before (string resolves by class name)
        -5: ValidationLane,     # before, but after Preprocess
        0:  PostProcessLane,    # after this lane
        10: CleanupLane,        # after PostProcess
        20: None,               # remove whatever was at priority 20
    }

    def process(self, value):
        return transform(value)
```

Sub-lanes are recursive — a lane's `lanes` map can reference lanes with their
own `lanes` maps.

## Running

```python
result  = Lane.start("MAIN")        # run a primary lane by name
results = [*Lane.start("MAIN")]     # start() is iterable; collect all results
for r in Lane.start("MAIN"):
    print(r)
```

Names match the lane's class name uppercased (`Main` -> `"MAIN"`); `start` may
match multiple primary lanes.

## Data-source lanes

Generate data instead of consuming upstream input — just `yield`:

```python
class DataSourceLane(Lane):
    @classmethod
    def primary(cls) -> bool:
        return True

    def process(self, value):
        for item in fetch_data_from_source():
            yield item
```

## Async lanes

`AsyncLane` mirrors `Lane` — same `lanes`, priorities, `primary()`, `start()` —
but `process`/`run`/`start` are coroutines / async generators:

```python
import asyncio
from l2l import AsyncLane

class FetchLane(AsyncLane):
    async def process(self, value):
        data = await fetch(value)
        yield data

class Main(AsyncLane):
    lanes = {1: FetchLane}

    @classmethod
    def primary(cls) -> bool:
        return True

    async def process(self, value):
        await asyncio.sleep(0)
        yield "start"

async def main():
    async for result in AsyncLane.start("MAIN"):   # start() is an async generator
        print(result)

asyncio.run(main())
```

- `process` can be `async def` returning a value, a sync generator, or an async
  generator (`async def` with `yield`).
- Inputs may be plain values, sync generators, or async generators.

## l2l public API (`from l2l import ...`)

`Lane`, `AsyncLane`, `Mock` (test helper), `TerminateKind` (termination enum),
`events` (event hooks), `logger`, `style`.

## l2l gotchas

- Not an entry point unless `primary()` returns `True`.
- Priority sign matters: negative before, positive after; ordering by magnitude.
- `yield` multiple items downstream; `return` a single value.
- String lane references resolve by class name — keep names unique.

---

# Part 2 — carabao: the framework

## Recognizing a carabao project

A `carabao.cfg`, a `settings.py` subclassing `carabao.Settings`, a `lanes/`
directory of `Lane` subclasses, `.env.development`/`.env.release` files, or
`carabao` in `pyproject.toml`/requirements.

`carabao.cfg` points the framework at the settings module:

```ini
[directories]
settings = src.settings
```

`settings.py` declares where lanes live + runtime behavior:

```python
from carabao import Settings as S

class Settings(S):
    LANE_DIRECTORIES = ["lanes"]   # dirs scanned for Lane subclasses
    SINGLE_RUN = False
    SLEEP_MIN = 1.0
    SLEEP_MAX = 3.0
    EXIT_ON_FINISH = False
    EXIT_DELAY = 0.0
    PROCESSES = 1
    DEPLOY_SAFELY = True

    @classmethod
    def error_handler(cls, error: Exception) -> None: ...

    @classmethod
    def before_start(cls) -> None: ...
```

Read at runtime:

```python
from carabao.settings import Settings
value = Settings.get().value_of("LANE_DIRECTORIES")
```

Any setting is overridable by an env var of the same name.

## The `moo` CLI

The app starts via the CLI — **no import/entrypoint needed**:

```sh
moo init [--skip]   # scaffold a project (settings.py, carabao.cfg, .env files)
moo new MyLaneName  # create a lane file (snake_case file, PascalCase class)
moo dev [queue]     # development mode (interactive selector + live UI if no queue)
moo run [queue]     # production mode
```

To run for the user, prefer `moo dev <lane>` (direct) or `moo run`. `moo dev`
with no queue opens an interactive Textual selector — **avoid in
non-interactive shells** (it blocks); pass the lane name.

Interactive dev UI needs the `standard` extra: `pip install "carabao[standard]"`.
Core runtime (`moo run`, `moo dev <lane>`) works without it.

## Forms — typed inputs for the dev selector

A lane may declare an inner `Form`; the `moo dev` selector prompts for these
before running. Read values via the global `F`:

```python
from l2l import Lane
from carabao import F, Field

class Main(Lane):
    class Form:
        source: str = "synthetic"   # str -> text input
        batch_size: int = 100       # int/float -> number input
        threshold: float = 0.5
        dry_run: bool = False       # bool -> checkbox
        workers = Field(cast=int, default=4, min_value=1, max_value=8, step=1)  # slider

    @classmethod
    def primary(cls) -> bool:
        return True

    def process(self, value):
        if F.dry_run:
            ...
        print(F.source, F.batch_size, F.workers)
```

- Annotations map to widgets: `str`→text, `int`/`float`→number, `bool`→checkbox.
- `Field(cast=..., min_value=..., max_value=..., step=...)` renders a slider.
- Read with `F.<name>` or `F["<name>"]`. Selector remembers last values per lane.
- Forms are optional.

## Database hubs

Imported from the top-level package; each needs its driver installed (e.g.
`pip install "fun-things[mongo,redis]" psycopg2-binary`):

- `mongo` — pymongo
- `redis` — redis
- `es` — elasticsearch
- `pg` — postgres
- `amongo` — async pymongo (`AsyncMongoClient`), for `AsyncLane`
- `aredis` — `redis.asyncio`, for `AsyncLane`

```python
from carabao import mongo, redis, amongo, aredis  # import only what you need
```

Imports are guarded — a missing driver silently disables that hub; guard usage
or ensure the driver is installed.

## Breakpoints (dev only)

Inside `process()`, call `self.breakpoint("label")` to pause under `moo dev`
(inspect payload in the UI Value tab, press `c` to continue). **No-op under
`moo run`** — safe to leave in.

## Key environment variables

- `QUEUE_NAME` (required) — queue to consume
- `CARABAO_AUTO_INITIALIZE`, `CARABAO_AUTO_START`, `CARABAO_START_WITH_ERROR`
- `SINGLE_RUN` — run once then exit
- `TESTING` — debug logging
- `CARABAO_LOG_MAX_LINES` (10000), `CARABAO_LOG_PAGE_SIZE` (200) — dev UI log buffer

Env files by mode: `.env.development` (`moo dev`), `.env.release` (`moo run`),
`.env` (fallback). Precedence: system env > matching .env file > settings defaults.

## carabao public API (`from carabao import ...`)

`Core`, `Settings`, `start`, `C` (constants), `Form`, `F`, `Field`, and db hubs
`mongo`, `redis`, `es`, `pg`, `amongo`, `aredis`. `carabao.start()` (wraps
`Core.start()`) is the programmatic entry point, but normal use is the `moo` CLI.

## carabao gotchas

- Lanes are discovered by scanning `LANE_DIRECTORIES`; a new lane file must live
  there. Use `moo new` for correct naming.
- `primary()` returning `True` makes a lane runnable/selectable.
- Don't open `moo dev` with no queue in a non-interactive shell — it blocks on a
  Textual UI. Pass the lane name.
- The dev UI is an optional extra; if interactive screens error, install
  `carabao[standard]`.
