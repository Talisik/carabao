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

A Python library for building robust publisher-subscriber (pub/sub) frameworks with built-in lanes for common tasks.

## Features

-   Core framework for managing pub/sub systems based on l2l (lane2lane)
-   Built-in lanes for:
    -   Database logging (`LogToDB`) - Records exceptions to MongoDB
    -   Network health monitoring (`NetworkHealth`) - Tracks network ping times
    -   Environment variable display (`PrettyEnv`) - Formats environment variables for debugging
-   Automatic configuration management with settings system
-   Error handling with custom error handlers
-   Clean shutdown with exit handlers
-   Command-line interface for management, including interactive selection
-   Support for multiple database connections (MongoDB, Redis, Elasticsearch, PostgreSQL)
-   Development and production mode support

## Installation

```sh
pip install carabao
```

## Requirements

-   async-timeout
-   dnspython
-   fun-things
-   generic-lane
-   lazy-main
-   python-dotenv
-   simple-chalk
-   typing-extensions

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

This makes it easy to maintain different configurations for development and production environments without changing code.

### Settings System

Carabao uses a centralized Settings system for configuration management. The Settings class provides a unified interface for accessing configuration values throughout the application.

#### Setting Up settings.py

A typical settings.py file inherits from the base Settings class, following the approach shown in the sample settings file:

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

    # Custom error handler function
    @classmethod
    def error_handler(cls, error: Exception) -> None:
        """
        Custom error handler for the application.

        Args:
            error: The exception that was raised.
        """
        print(f"An error occurred: {error}")
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

    You can also define your own custom settings and access them the same way.

4. **Overriding Settings**:
   Settings can be overridden by environment variables. For example, if your setting is named `SINGLE_RUN`, you can override it by setting the `SINGLE_RUN` environment variable.

### CLI Usage

Carabao provides a command-line interface for managing lanes:

```sh
# Run in production mode
moo run

# Run in development mode
moo dev [queue_name]

# Initialize a new project
moo init [--skip]

# Create a new lane
moo new [lane_name]
```

The development mode (`dev`) command:

-   If no queue name is provided, displays an interactive curses-based menu to select from available lanes
-   Highlights the last run queue
-   Provides navigation with arrow keys
-   Allows selection with Enter key
-   Exit option at the bottom

## Built-in lanes

Carabao comes with several built-in lanes that provide common functionality:

### LogToDB

A passive lane that logs exceptions to a MongoDB database.

```python
from carabao.lanes import LogToDB
from pymongo import MongoClient

# Configure MongoDB connection
client = MongoClient("mongodb://localhost:27017/")
db = client["my_database"]
collection = db["error_logs"]

# Configure LogToDB lane
LogToDB.storage = collection
LogToDB.label = "my_app"  # Optional, defaults to POD_NAME
LogToDB.expiration_time = timedelta(days=7)  # Optional, defaults to 1 hour
LogToDB.use_stacktrace = True  # Optional, defaults to True
```

Key features:

-   Automatically captures and logs exceptions to MongoDB
-   Configurable document expiration time
-   Options to use stack traces or simple error messages
-   Customizable document format

### NetworkHealth

Monitors network health by measuring ping times and stores the metrics in MongoDB.

```python
from carabao.lanes import NetworkHealth
from pymongo import MongoClient

# Configure MongoDB connection
client = MongoClient("mongodb://localhost:27017/")
db = client["my_database"]
collection = db["network_health"]

# Configure NetworkHealth lane
NetworkHealth.storage = collection
NetworkHealth.label = "api_service"  # Optional identifier
```

Key features:

-   Tracks network ping times
-   Stores metrics in a MongoDB collection
-   Updates records with timestamps for monitoring

### PrettyEnv

Displays environment variables in a formatted way to aid in debugging and configuration.

```python
# Automatically called if enabled. No configuration needed for PrettyEnv.
```

Key features:

-   Displays all accessed environment variables
-   Formatted for easy reading
-   Useful for debugging configuration issues

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
