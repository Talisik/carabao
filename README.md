# Carabao

```
                                                           +:
   -                                                        *-
  -*                                                        +--
 -*                                                          *=:
-=*                                                         +=+-
-+*                                                        +==*-
++=*                                                      **=+-
 *==*+                                                 -**==*-
  -***=*++                                         -*=**=**-%
   %-****=*===----------#*%*##+%#@#**-*---------===**+=-%-#
      **=-***-=*==*==--****%#%%@*@@%#*-----+*=++%++++%%*
          *%%%#%####%##%*#%%=##@++%@%%######%%%%#%@
               + @%@@@@##%#=@#@@+++@@%
             --+++++##%@%#=@@+@@%%@#@#++++=%
           @+*@@@@@@##@##*=**+*@%%%@#@+@@#@++%
              #*       *#**##+#%%%*@ %%%%++++#+
                       *+****+#%%%*@
                       **=*==+#%##*
                        *=*=+*#%#*
                        #=*****#*
                       #@=***#@##
                       %%=%%%#=#%#
                       ####%%%#
```

[GitHub](https://github.com/Talisik/carabao)
[PyPI](https://pypi.org/project/carabao/)

A Python library for building robust publisher-subscriber (pub/sub) frameworks with built-in lanes for common tasks.

## Features

-   Core framework for managing pub/sub systems based on l2l (lane2lane)
-   Live RAM / CPU / network stats in the dev UI status bar (when `psutil` is installed)
-   Automatic configuration management with settings system
-   Error handling with custom error handlers
-   Clean shutdown with exit handlers
-   Command-line interface for management, including interactive selection
-   Support for multiple database connections (MongoDB, Redis, Elasticsearch, PostgreSQL)
-   Development and production mode support
-   Test mode for safe testing in production environments

## Installation

```sh
pip install carabao
```

The interactive developer UI (the `moo dev` selector + live visualizer) is
**optional** — it ships in the `standard` extra (à la `fastapi[standard]`):

```sh
pip install "carabao[standard]"
```

Without the extra, the core runtime (`moo run`, `moo dev <lane>`) works fully;
only the interactive screens require it (you'll get a clear message prompting
the install if you open them without it).

The database hubs (MongoDB, Redis, Elasticsearch, PostgreSQL) need their drivers
installed separately — e.g. `pip install "fun-things[mongo,redis]" psycopg2-binary`.

## Requirements

Core: `async-timeout`, `dnspython`, `fun-things`, `lazy-main`, `python-dotenv`,
`typing-extensions`, `typer`, `lane2lane`.

`standard` extra (interactive UI): `textual`, `textual-slider`.

## Usage

### Basic Usage

The framework is started using the CLI commands:

```sh
# For development mode
moo dev [queue_name]

# For production mode
moo run
```

No import statement is needed to start the framework.

### Forms

A lane can declare a `Form` — typed inputs the `moo dev` selector prompts for
before running. Define an inner `Form` class with annotated attributes (or
`Field(...)` for a bounded numeric slider), then read the values anywhere via
the global `F`:

```python
from l2l import Lane

from carabao import F, Field


class Main(Lane):
    class Form:
        source: str = "synthetic"   # text input
        batch_size: int = 100       # number input
        threshold: float = 0.5
        dry_run: bool = False       # checkbox
        workers = Field(cast=int, default=4, min_value=1, max_value=8, step=1)  # slider

    @classmethod
    def primary(cls) -> bool:
        return True

    def process(self, value):
        if F.dry_run:
            ...
        print(F.source, F.batch_size, F.workers)
```

-   Plain annotations become typed inputs: `str` → text, `int`/`float` → number,
    `bool` → checkbox.
-   `Field(cast=int, min_value=…, max_value=…, step=…)` renders a slider.
-   Read values with `F.<name>` (or `F["<name>"]`). The selector remembers the
    last-entered values per lane.
-   Forms are optional — a lane without one just runs.

![Form inputs in the dev selector](https://raw.githubusercontent.com/Talisik/carabao/main/previews/form.jpg)

### Environment Variables

Carabao uses the following environment variables:

-   `QUEUE_NAME`: (Required) Name of the queue to consume
-   `CARABAO_AUTO_INITIALIZE`: Controls automatic initialization
-   `CARABAO_AUTO_START`: Controls automatic starting
-   `CARABAO_START_WITH_ERROR`: Whether to start even if errors occurred
-   `SINGLE_RUN`: Run once then exit if `True`
-   `TESTING`: Enable debug logging if `True`

### Environment Files

Carabao supports environment variables loaded from `.env` files using python-dotenv:

-   `.env.development`: Used when running in development mode (`moo dev`)
-   `.env.release`: Used when running in production mode (`moo run`)
-   `.env`: Used as a fallback if neither of the above files exists

When initializing a new project with `moo init`, these files are automatically created.

The framework prioritizes environment variables in the following order:

1. Variables defined in the system environment
2. Variables defined in the appropriate .env file
3. Default values defined in settings

This makes it easy to maintain different configurations for development, testing, and production environments without changing code.

### Settings System

Carabao uses a centralized Settings system for configuration management. The Settings class provides a unified interface for accessing configuration values throughout the application.

#### Setting Up settings.py

A typical settings.py file inherits from the base Settings class:

```python
from carabao import Settings as S


class Settings(S):
    # Directory where the lane modules are stored
    LANE_DIRECTORIES = [
        "lanes",
    ]

    # Whether to run the pipeline once and exit
    SINGLE_RUN = False

    # Minimum and maximum sleep times between runs (in seconds)
    SLEEP_MIN = 1.0
    SLEEP_MAX = 3.0

    # Whether to exit when processing is finished
    EXIT_ON_FINISH = False

    # Delay before exiting (in seconds)
    EXIT_DELAY = 0.0

    # Number of parallel processes to use
    PROCESSES = 1

    # Whether to deploy safely in production
    DEPLOY_SAFELY = True

    # Custom error handler function
    @classmethod
    def error_handler(cls, error: Exception) -> None:
        """
        Custom error handler for the application.

        Args:
            error: The exception that was raised.
        """
        print(f"An error occurred: {error}")

    @classmethod
    def before_start(cls) -> None:
        """
        Hook method called before framework startup.
        """
        # Perform any necessary initialization
        pass
```

When you run `moo init`, this file is automatically created for you in the appropriate location.

#### Settings Configuration

1. **carabao.cfg File**:
   The framework uses a configuration file to locate your settings module:

    ```
    [directories]
    settings = src.settings  # or path.to.your.settings
    ```

2. **Accessing Settings in Code**:
   To use these settings in your code:

    ```python
    from carabao.settings import Settings

    settings = Settings.get()
    value = settings.value_of("LANE_DIRECTORIES")
    ```

3. **Available Settings**:
   Common settings include:

    - `LANE_DIRECTORIES`: List of directories to search for lane definitions
    - `SINGLE_RUN`: Whether to run lanes once or continuously
    - `SLEEP_MIN`, `SLEEP_MAX`: Minimum and maximum sleep times between runs
    - `EXIT_ON_FINISH`: Whether to exit after finishing processing
    - `EXIT_DELAY`: Delay before exiting
    - `PROCESSES`: Number of parallel processes to use
    - `DEPLOY_SAFELY`: Whether to enforce production safety settings

    You can also define your own custom settings and access them the same way.

4. **Overriding Settings**:
   Settings can be overridden by environment variables. For example, if your setting is named `SINGLE_RUN`, you can override it by setting the `SINGLE_RUN` environment variable.

### CLI Usage

Carabao provides a command-line interface for managing lanes:

```sh
# Run in production mode
moo run [queue_name]

# Run in development mode
moo dev [queue_name]

# Initialize a new project
moo init [--skip]

# Create a new lane
moo new [lane_name]
```

### Development UI (`moo dev`)

Requires the `standard` extra (`pip install "carabao[standard]"`).

**Selector.** `moo dev` (no queue name) opens an interactive screen:

-   Lists every available primary lane — both sync (`Lane`) and async
    (`AsyncLane`).
-   Shows the selected lane's docstring and a **process tree** built from its
    `lanes` field (recursive — sub-lanes appear automatically).
-   Edits the lane's form fields (if it defines a `Form`).
-   Toggles: **🧪 Test** and **📊 UI** (the live visualizer; on by default).
-   Remembers your last selection. `Enter` runs, `Esc` exits.

![The dev queue selector](https://raw.githubusercontent.com/Talisik/carabao/main/previews/queue_selection.jpg)

`moo dev <queue_name>` skips the selector and runs that lane directly.

**Live UI.** With the **📊 UI** toggle on, running a lane opens a live dashboard.

The **left panel** has tabs (cycle with **`q`** / **`e`**):

-   **Lanes** — the full pipeline laid out from the `lanes` field up front; each
    lane spins while active and shows its true work time when done.
-   **Env** — the loaded `.env` file(s) and the env vars actually read.
-   **Value** — the latest value flowing between lanes (type · count · bytes),
    as pretty JSON.

The **log pane** captures `print()`, the `l2l` logger, **loguru**, and the
stdlib `logging` module (including non-propagating loggers):

-   selectable text (drag to select, double-click a word, triple-click a line,
    `Ctrl+C` to copy)
-   syntax-highlighted JSON, colored tracebacks, and inline markdown
    (`**bold**`, `` `code` ``, `*italic*`, `~~strike~~`)
-   optional `module:func:line` origin per line

![The log pane](https://raw.githubusercontent.com/Talisik/carabao/main/previews/logs.jpg)

The **bottom bar** is a compact control strip:

-   **`/`** reveals a search box (hides again when empty)
-   **`f`** swaps in the level filters, **`d`** the display toggles — **number
    keys** toggle each item; `TRACE` is off by default
-   live RAM / CPU / network (when `psutil` is installed) and an elapsed timer

![Search box and the Environment tab](https://raw.githubusercontent.com/Talisik/carabao/main/previews/search_and_env.jpg)

**Breakpoints.** Call `self.breakpoint("label")` inside `process()` to pause the
pipeline (dev-only — a no-op under `moo run`). The lane shows `⏸`, logs at the
`PAUSE` level, and the timer freezes; inspect the payload in the **Value** tab,
then press `c` to continue.

![Breakpoints and the Value tab](https://raw.githubusercontent.com/Talisik/carabao/main/previews/breakpoints_and_value.jpg)

The **status bar** shows live RAM / CPU / network (when `psutil` is installed)
and an elapsed timer — `Done in <time>` (green) or `Error: …` (red) on
completion. `Esc` quits (confirms first if still running; the hotkey turns red
once it's safe to exit).

Async lanes are detected automatically and run via `asyncio`; the core runtime
(`moo run`) carries no overhead from any of the UI instrumentation.

## Development

### Creating a New Project

You can quickly initialize a new project with:

```sh
moo init
```

This will set up the necessary directory structure and configuration files.

### Creating a New Lane

To create a new lane for processing:

```sh
moo new MyLaneName
```

This will generate a file with proper naming conventions (snake_case for the filename, PascalCase for the class name).
