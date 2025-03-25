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

A Python library for building pub/sub consumer-based frameworks.

## Installation

```sh
pip install git+https://github.com/Talisik/carabao.git
```

## Features

- Built on top of generic-consumer for robust pub/sub functionality
- Pre-configured connections to Redis and MongoDB
- Automatic consumer registration and queue naming
- Configurable batch processing
- Environment-based configuration
- Support for different deployment environments (staging, production)
- Graceful error handling and recovery
- CLI interface for managing consumers
- Minimal boilerplate code required

## Quick Start

Simply import the package to automatically initialize and start the framework:

```python
import carabao

# Your application code here
```

## Architecture

Carabao follows a publisher-subscriber architecture:

1. **Publishers** send messages to named queues
2. **Consumers** process messages from specific queues
3. **Core Framework** handles connections, message routing, and lifecycle management

The framework automatically discovers and registers consumer classes, manages connections to Redis and MongoDB, and handles the message processing lifecycle.

## Consumer Framework

### Creating Consumers

Extend the base consumer classes to create your own consumers:

```python
from carabao.consumers import BaseConsumer

class MyConsumer(BaseConsumer):
    def process(self, message):
        # Process your message here
        print(f"Processing: {message}")
```

### Queue Names

Queue names are automatically generated based on the class name, in uppercase separated by underscores:

```python
class HelloWorld(BaseConsumer): # Queue name: HELLO_WORLD
    pass

class AISearch(BaseConsumer): # Queue name: AI_SEARCH
    pass

class RedditETL1(BaseConsumer): # Queue name: REDDIT_ETL_1
    pass
```

You can override this behavior:

```python
class HelloWorld(BaseConsumer):
    @classmethod
    def queue_name(cls):
        return "MY_CUSTOM_QUEUE_NAME"
```

## Built-in Consumers

Carabao comes with a few built-in consumers:

- **PrettyEnv**: Outputs environment variables in a readable format
- **NetworkHealth**: Monitors network connectivity and service health
- **LogToDB**: Logs exceptions to a MongoDB database

### Using LogToDB Consumer

The LogToDB consumer is designed to capture and store exceptions in a MongoDB collection.

```python
from carabao.consumers import LogToDB
from pymongo import MongoClient

# Connect to MongoDB and get collection
client = MongoClient("mongodb://localhost:27017/")
db = client["your_database"]
collection = db["exceptions"]

# Configure LogToDB
LogToDB.name = "your_service_name"  # Default is POD_NAME
LogToDB.storage = collection  # Must be a MongoDB collection

# Now any exceptions caught by the framework will be logged to the database
```

The LogToDB consumer stores exception data in the following format:

```python
@dataclass
class Document:
    name: str  # Service/pod name
    exceptions: List[str]  # List of exception strings
    date_created: datetime  # UTC timestamp
```

You can customize how documents are converted to dictionaries by setting the `document_selector` attribute:

```python
LogToDB.document_selector = your_custom_document_converter_function
```

## CLI Commands

Carabao includes a command-line interface for managing consumers:

```sh
# Run a specific consumer
carabao run --queue QUEUE_NAME

# See all available commands
carabao --help
```

## Configuration

The following environment variables can be used to configure the framework:

### Core Settings

- `ENVIRONMENT` (str): Deployment environment (`staging` or `production`). Default: `staging`
- `SINGLE_RUN` (bool): If consumers should only run once. Default: `True`
- `QUEUE_NAME` (str) [REQUIRED]: Consumers with the same name are selected
- `BATCH_SIZE` (int): Number of payloads retrieved at once. Default: `1`
- `POD_NAME` (str): Name of the current pod in Kubernetes environments. Default: `None`
- `POD_INDEX` (int): Index of the current pod in Kubernetes environments. Default: `0`

### MongoDB Settings

- `MONGO_URI` (str): MongoDB connection string. Default: `mongodb://localhost:27017/`
- Aliases: `MONGO_CONNECTION_STRING`, `MONGO_CONNECTION_URI`

### Redis Settings

- `REDIS_HOST` (str): Redis host. Default: `localhost`
- `REDIS_PORT` (int): Redis port. Default: `6379`
- `REDIS_PASSWORD` (str): Redis password. Default: `None`
- `REDIS_READ_ONLY_HOST` (str): Redis read-only host. Default: `None`
- `REDIS_READ_ONLY_PORT` (int): Redis read-only port. Default: `0`
- `REDIS_READ_ONLY_PASSWORD` (str): Redis read-only password. Default: `None`

### Runtime Settings

- `SLEEP_MIN` (float): Minimum sleep time between runs in seconds. Default: `3`
- `SLEEP_MAX` (float): Maximum sleep time between runs in seconds. Default: `5`
- `EXIT_ON_FINISH` (bool): Call `exit(0)` when session is done. Default: `True`
- `EXIT_DELAY` (float): Delay before exit in seconds. Default: `3`

### Framework Initialization

- `CARABAO_AUTO_INITIALIZE` (bool): Auto-initialize framework. Default: `True`
- `CARABAO_AUTO_START` (bool): Auto-start framework on program termination. Default: `True`
- `CARABAO_START_WITH_ERROR` (bool): Allow auto-start with errors. Default: `False`

## Dependencies

Carabao requires the following Python packages:

- async-timeout
- dnspython
- fun-things
- generic-consumer
- lazy-main
- python-dotenv
- simple-chalk
- typing-extensions

## License

See the [LICENSE](LICENSE) file for details.