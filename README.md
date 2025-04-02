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

A Python library for building robust publisher-subscriber (pub/sub) frameworks with built-in lanes for common tasks.

## Features

- Core framework for managing pub/sub systems
- Built-in lanes for:
  - Database logging (`LogToDB`)
  - Network health monitoring (`NetworkHealth`)
  - Environment variable display (`PrettyEnv`)
- Automatic configuration management
- Error handling with custom error handlers
- Clean shutdown with exit handlers
- Command-line interface for management

## Installation

```sh
pip install git+https://github.com/Talisik/carabao.git
```

## Requirements

- async-timeout
- dnspython
- fun-things
- generic-lane
- lazy-main
- python-dotenv
- simple-chalk
- typing-extensions

## Usage

### Basic Usage

```python
if __name__ == "__main__":
    import carabao
```

### Environment Variables

Carabao uses the following environment variables:

- `QUEUE_NAME`: (Required) Name of the queue to consume
- `CARABAO_AUTO_INITIALIZE`: Controls automatic initialization
- `CARABAO_AUTO_START`: Controls automatic starting
- `CARABAO_START_WITH_ERROR`: Whether to start even if errors occurred
- `SINGLE_RUN`: Run once then exit if `True`
- `TESTING`: Enable debug logging if `True`

### CLI Usage

Carabao provides a command-line interface for managing lanes:

```sh
carabao [command] [options]
```

#### Available Commands

- `run [queue_name]`: Start a lane for the specified queue
  - If no queue name is provided, displays an interactive curses-based menu to select from available lanes
  - Example: `carabao run MY_QUEUE`

The interactive menu displays:

- A list of available lane queues
- Highlights the last run queue
- Provides navigation with arrow keys
- Allows selection with Enter key
- Exit option at the bottom

The CLI automatically reads and updates the configuration file to track the last run queue and available lanes.

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
LogToDB.name = "my_app"  # Optional, defaults to POD_NAME
LogToDB.expiration_time = timedelta(days=7)  # Optional, defaults to 1 hour
LogToDB.use_stacktrace = True  # Optional, defaults to True
```

Key features:

- Automatically captures and logs exceptions to MongoDB
- Configurable document expiration time
- Options to use stack traces or simple error messages
- Customizable document format

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
NetworkHealth.name = "api_service"  # Optional identifier
```

Key features:

- Tracks network ping times
- Stores metrics in a MongoDB collection
- Updates records with timestamps for monitoring

### PrettyEnv

Displays environment variables in a formatted way to aid in debugging and configuration.

```python
# Automatically called. No configuration needed for PrettyEnv.
```

Key features:

- Displays all accessed environment variables
- Formatted for easy reading
- Useful for debugging configuration issues

## Development
