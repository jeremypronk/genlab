# API

* [.](#.)
  * [handle\_http\_exceptions](#..handle_http_exceptions)
  * [setup\_logging](#..setup_logging)
  * [GenAPI](#..GenAPI)
    * [PLATFORM](#..GenAPI.PLATFORM)
    * [upload\_file](#..GenAPI.upload_file)
    * [upload\_files](#..GenAPI.upload_files)
    * [write\_payload](#..GenAPI.write_payload)
    * [read\_payload](#..GenAPI.read_payload)
    * [download\_file](#..GenAPI.download_file)
    * [is\_finished](#..GenAPI.is_finished)
    * [prep\_param](#..GenAPI.prep_param)
    * [prep\_task](#..GenAPI.prep_task)
    * [prep\_task\_from\_file](#..GenAPI.prep_task_from_file)
    * [prep\_task\_from\_id](#..GenAPI.prep_task_from_id)
    * [submit\_task](#..GenAPI.submit_task)
    * [query\_task](#..GenAPI.query_task)
* [kieai](#kieai)
  * [KieAIGen](#kieai.KieAIGen)
    * [prep\_param](#kieai.KieAIGen.prep_param)
    * [query\_task](#kieai.KieAIGen.query_task)

# .

#### handle\_http\_exceptions

```python
def handle_http_exceptions(func)
```

A decorator that wraps a function with a try-except block for common
requests errors. Unhandled exceptions are allowed to propagate.

#### setup\_logging

```python
def setup_logging(
        debug: bool = False,
        log_file: Optional[Union[str, Path]] = "genlab.log") -> logging.Logger
```

Configures the root logger for application and test usage.

## GenAPI

```python
class GenAPI()
```

#### PLATFORM

subclass should override this as a metadata identifier for the API implemented

#### upload\_file

```python
@handle_http_exceptions
def upload_file(path: str | Path) -> str | None
```

Uploads a file via http. Caches upload files to only upload once.
If path is already a url, simply returns path.

**Arguments**:

- `path` - path to upload
  

**Returns**:

  url of uploaded file

#### upload\_files

```python
def upload_files(files: list | str | Path) -> list[str | None]
```

Upload a list of files.

**Arguments**:

- `files` - list of file paths
  

**Returns**:

  list of urls of uploaded files

#### write\_payload

```python
def write_payload(file_path)
```

Write payload to file metadata.
Only makes sense after prep_task has been run.

**Arguments**:

- `file_path` - path to file to write payload metadata
  

**Returns**:

  success

#### read\_payload

```python
def read_payload(cls, file_path) -> dict
```

Read payload from file metadata.

**Arguments**:

- `file_path` - path to file to read
  

**Returns**:

  tuple of str, dict - platform id str and payload from file

#### download\_file

```python
@handle_http_exceptions
def download_file(url: str, output_path: str | Path) -> int
```

Download a file via http.

**Arguments**:

- `url` - url of the file to download
- `output_path` - path to save the downloaded file
  

**Returns**:

  size of downloaded file in bytes

#### is\_finished

```python
def is_finished(task_status) -> bool
```

Check task status for "finished" status.

**Arguments**:

- `task_status` - the status of the task one of GenAPI.TASK_STATUS
  

**Returns**:

  bool True if finished (not still running)

#### prep\_param

```python
def prep_param(param, value) -> tuple
```

Can be called for each payload param,value pair when preparing the task/request.
Base version simply returns the param,value pair.
Override for additional processing, eg to upload local reference and return the url.

**Arguments**:

  param task/request parameter
  value task/request value
  

**Returns**:

  tuple of task ready param,value pair.

#### prep\_task

```python
def prep_task(input_payload) -> bool
```

Perform pre task/request operations.
Subclass must implement this and also call this function.

**Arguments**:

  dict task/request payload
  

**Returns**:

  bool success

#### prep\_task\_from\_file

```python
def prep_task_from_file(file_path) -> bool
```

Perform pre task/request operations reading input payload from the given file.

**Arguments**:

  file_path path to the file the task payload metadata embedded
  

**Returns**:

  bool success

#### prep\_task\_from\_id

```python
def prep_task_from_id(input_payload, task_id) -> bool
```

Perform pre task/request operations for a previously submitted task.

**Arguments**:

  dict task/request payload
  task_id task/request id of the existing task/request
  

**Returns**:

  bool success

#### submit\_task

```python
def submit_task() -> str
```

Submit the task/request.
Previously submitted tasks (where task_id is already set) will not be re-submitted.
Subclass must implement this method.

**Returns**:

  str task/request id

#### query\_task

```python
def query_task() -> tuple
```

Query the status of the task/request.
Subclass must implement this method.

**Returns**:

  tuple of (TASK_STATUS, response_json)

# kieai

## KieAIGen

```python
class KieAIGen(GenAPI)
```

Concrete implementation of the kie.ai API
https://docs.kie.ai/

You can pass your api key in the environment variable KIE_API_KEY or to the class constructor

#### prep\_param

```python
def prep_param(param, value) -> tuple
```

kie.ai legacy image payload params are named image_input and video payload image and video reference params
all end in _url (single ref) or _urls (list of refs).
Uploads url params if they contain a path to a local file, replacing path value with the new url.
(upload_file() handles input urls by simple returning the input path)

**Arguments**:

  param task/request parameter
  value task/request value
  

**Returns**:

  tuple of task ready param,value pair.

#### query\_task

```python
@handle_http_exceptions
def query_task() -> tuple
```

For details on the contents of the task response see,
https://docs.kie.ai/market/common/get-task-detail

