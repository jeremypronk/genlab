import os
import posixpath
import ntpath
from pathlib import Path
import re
import yaml
from enum import Enum
import functools
import logging
import requests
import sys
from typing import Union, Optional


class YamlParamReplacer:
    """
    Reads a YAML file of parameter name/value pairs and replaces matching
    tokens in a target YAML object with their associated values.

    Token format: ``{{ PARAM_NAME }}``  (whitespace around the name is ignored)

    Example ``params.yaml``::

        database_host: localhost
        app_port: 8080
        env: production

    Example ``target.yaml``::

        db:
            host: "{{ database_host }}"
            port: "{{ app_port }}"
        environment: "{{ env }}"
    """

    #: Regex that matches ``{{ PARAM_NAME }}`` with optional inner whitespace.
    TOKEN_PATTERN: re.Pattern = re.compile(r"\{\{\s*(\w+)\s*\}\}")

    def __init__(self, params_yaml_path: str) -> None:
        """
        Initialise the replacer by loading a YAML file of parameter name/value pairs.

        Args:
            params_yaml_path: Path to the YAML file containing parameter definitions.

        Raises:
            FileNotFoundError: If the params YAML file does not exist.
            ValueError: If the params YAML file is empty or not a key/value mapping.
        """
        path = Path(params_yaml_path)
        if not path.exists():
            raise FileNotFoundError(f"Params file not found: {params_yaml_path}")

        with open(path, "r", encoding="utf-8") as fh:
            params = yaml.safe_load(fh)

        if params is None:
            raise ValueError(f"Params file is empty: {params_yaml_path}")
        if not isinstance(params, dict):
            raise ValueError(
                f"Params file must be a YAML mapping (key: value pairs), "
                f"got {type(params).__name__}: {params_yaml_path}"
            )

        # Coerce all values to strings so substitution is always safe.
        self.params: dict[str, str] = {k: str(v) for k, v in params.items()}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def replace_tokens(self, target: object) -> object:
        """
        Recursively walk *target* (a loaded YAML object) and replace every
        token that matches a parameter name with the corresponding value.

        Tokens use the format ``{{ PARAM_NAME }}`` anywhere inside a string
        value. Multiple tokens may appear within a single string.

        Type coercion is attempted only when the **entire** string is a single
        token (e.g. ``"{{ app_port }}"`` → ``8080`` as an ``int``). Mixed
        strings such as ``"http://{{ host }}/path"`` remain plain strings.

        Unknown tokens are left unchanged so callers can detect them separately.

        Args:
            target: A Python object produced by ``yaml.safe_load`` — typically
                    a ``dict``, ``list``, or scalar.

        Returns:
            A new object of the same structure with all known tokens replaced.
        """
        return self._walk(target)

    def replace_tokens_from_file(self, target_yaml_path: str) -> object:
        """
        Convenience method: load *target_yaml_path* then call
        :meth:`replace_tokens`.

        Args:
            target_yaml_path: Path to the YAML file to process.

        Returns:
            The updated YAML object with all known tokens replaced.

        Raises:
            FileNotFoundError: If *target_yaml_path* does not exist.
        """
        path = Path(target_yaml_path)
        if not path.exists():
            raise FileNotFoundError(f"Target file not found: {target_yaml_path}")

        with open(path, "r", encoding="utf-8") as fh:
            target = yaml.safe_load(fh)

        return self.replace_tokens(target)

    def get_params(self) -> dict[str, str]:
        """Return a shallow copy of the loaded parameter map."""
        return dict(self.params)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _walk(self, node: object) -> object:
        """Recursively traverse the YAML node tree."""
        if isinstance(node, dict):
            return {k: self._walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [self._walk(item) for item in node]
        if isinstance(node, str):
            return self._substitute(node)
        # int, float, bool, None — return as-is
        return node

    def _substitute(self, value: str) -> object:
        """
        Replace tokens inside *value*.

        * **Single-token strings** — attempt native type coercion on the result.
        * **Multi-token / mixed strings** — plain string substitution only.
        * **Unknown tokens** — left unchanged.
        """
        if not self.TOKEN_PATTERN.search(value):
            return value

        # If the entire string (ignoring surrounding whitespace) is exactly
        # one token, we can attempt type coercion after substitution.
        single_match = self.TOKEN_PATTERN.fullmatch(value.strip())
        if single_match:
            name = single_match.group(1)
            if name in self.params:
                return self._coerce(self.params[name])
            return value  # unknown token — leave unchanged

        # Multiple tokens or a token embedded within a larger string.
        def _replace(m: re.Match) -> str:
            return self.params.get(m.group(1), m.group(0))

        return self.TOKEN_PATTERN.sub(_replace, value)

    @staticmethod
    def _coerce(value: str) -> object:
        """
        Attempt to cast *value* to a native Python type.

        Order of precedence: ``bool`` → ``int`` → ``float`` → ``str``.
        The bool check must precede ``int`` because ``bool`` is a subclass of
        ``int`` in Python.
        """
        if value.lower() in ("true", "yes"):
            return True
        if value.lower() in ("false", "no"):
            return False
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass
        return value


class NetworkPathConverter:
    """
    OS-aware network path converter.
    Handles Windows (UNC/Drive) and macOS (Mounts) for str, bytes, and Path objects.
    """

    def __init__(self, mappings: list[dict] = None):
        """
        :param mappings: List of dicts, e.g., [{'win': 'P:', 'osx': '/Volumes/Projects'}]
        """
        # Sort by length descending to catch specific paths before generic drives
        self.mappings = sorted(
            mappings or [],
            key=lambda x: len(str(x.get('win', ''))),
            reverse=True
        )
        self._system_type = os.name  # 'nt' or 'posix'

    def _to_str(self, path) -> str:
        """Converts input (Path, bytes, str) to a standard string."""
        if isinstance(path, bytes):
            return path.decode('utf-8')
        if isinstance(path, Path):
            return str(path)
        return str(path) if path is not None else ""

    def _normalize_internal(self, path_str: str) -> str:
        """Standardizes all slashes to forward for internal prefix comparison."""
        return path_str.replace('\\', '/').rstrip('/')

    def convert(self, path, force_os: str = None):
        """
        Converts the path to the current system's format.
        Maintains the input type (str -> str, Path -> Path, bytes -> bytes).
        """
        if path is None:
            return None

        # Track original type for the return value
        original_type = type(path)
        path_str = self._to_str(path)

        if not path_str:
            return path  # Return empty of same type

        target_os = force_os if force_os else self._system_type
        is_target_win = (target_os == 'nt')
        clean_input = self._normalize_internal(path_str)

        result_str = None

        for m in self.mappings:
            win_pre = self._normalize_internal(str(m['win']))
            osx_pre = self._normalize_internal(str(m['osx']))

            match_win = clean_input.lower().startswith(win_pre.lower())
            match_osx = clean_input.lower().startswith(osx_pre.lower())

            if is_target_win:
                if match_osx:
                    rel = clean_input[len(osx_pre):].lstrip('/')
                    base = str(m['win'])
                    # Fix: Ensure drive letters (P:) get a backslash (P:\) before joining
                    if base.endswith(':') and len(base) == 2:
                        base += '\\'
                    result_str = ntpath.normpath(ntpath.join(base, rel.replace('/', '\\')))
                    break
                if match_win:
                    result_str = ntpath.normpath(path_str.replace('/', '\\'))
                    break

            else:  # Target is macOS / POSIX
                if match_win:
                    rel = clean_input[len(win_pre):].lstrip('/')
                    result_str = posixpath.normpath(posixpath.join(str(m['osx']), rel.replace('\\', '/')))
                    break
                if match_osx:
                    result_str = posixpath.normpath(path_str.replace('\\', '/'))
                    break

        # Fallback if no mapping matches
        if result_str is None:
            if is_target_win:
                result_str = ntpath.normpath(path_str.replace('/', '\\'))
            else:
                result_str = posixpath.normpath(path_str.replace('\\', '/'))

        # Cast back to original type
        if issubclass(original_type, Path):
            return original_type(result_str)
        if original_type is bytes:
            return result_str.encode('utf-8')

        return result_str



def handle_http_exceptions(func):
    """
    A decorator that wraps a function with a try-except block for common
    requests and file handling errors. This makes the decorated function
    cleaner by separating error handling from the main logic.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            # Attempt to execute the decorated function
            return func(*args, **kwargs)
        except requests.exceptions.HTTPError as http_err:
            logging.error(f"HTTP error occurred: {http_err}")
            # Log the response body if available, as it often contains useful error details.
            if http_err.response is not None:
                logging.error(f"Response Body: {http_err.response.text}")
        except requests.exceptions.RequestException as req_err:
            logging.error(f"A request error occurred: {req_err}")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")

        return None

    return wrapper

def setup_logging(
        debug: bool = False,
        log_file: Optional[Union[str, Path]] = "genlab.log"
) -> logging.Logger:
    """Configures the root logger for application and test usage."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Close and remove existing handlers to release file locks on Windows
    for handler in root_logger.handlers[:]:
        handler.close()
        root_logger.removeHandler(handler)

    # Handler 1: Console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    console_handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
    root_logger.addHandler(console_handler)

    # Handler 2: File (Optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
        )
        root_logger.addHandler(file_handler)

    return root_logger


class GenAPI:
    class TASK_STATUS(Enum):
        completed = 1
        failed = 2
        generating = 3
        waiting = 4
        queuing = 5
        unknown = 6

    JSON_HEADER = { "Content-Type": "application/json" }

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Automatically guarantees an isolated cache dict for each subclass
        if "UPLOAD_CACHE" not in cls.__dict__:
            cls.UPLOAD_CACHE = {}

    def __init__(self, output_basepath, task_id=None, path_converter_func=lambda x: x):
        self._output_basepath = Path(output_basepath)
        self._task_id = task_id
        self._path_converter_func = path_converter_func

        # Header sent with all http requests, subclasses should override this as required
        # typically used for authorisation
        self.HEADER = {}

    def __repr__(self):
        return f"{type(self).__name__}({self._task_id}, {self._output_basepath})"

    def _name(self):
        return self._output_basepath.stem

    def _log_msg(self, log_func, msg):
        log_func(f"({self._name()}) {msg}")

    def _info(self, msg):
        self._log_msg(logging.info, msg)

    def _warning(self, msg):
        self._log_msg(logging.warning, msg)

    def _error(self, msg):
        self._log_msg(logging.error, msg)

    def _debug(self, msg):
        self._log_msg(logging.debug, msg)

    def _check_api_response(self, response):
        """
        Basic api response check. Override this method in subclasses for more granular checking.
        Args:
            response: the response from the API (json string)

        Returns:
            bool True if response code is 200, False otherwise.
        """
        self._debug(f"GenAPI._check_api_response({response})")
        response_json = response.json()
        if response_json.get('code') == 200:
            self._debug("Request was successful.")
            return True

        if 'msg' in response_json:
            self._error(f"Error: API response code:- {response_json['code']} API response msg:- {response_json['msg']}")
        else:
            self._error(f"Unknown error ({response_json})")
        return False

    def is_finished(self, task_status):
        """
        Check task status for "finished" status.
        Args:
            task_status: the status of the task one of GenAPI.TASK_STATUS

        Returns:
            bool True if finished (not still running)
        """
        self._debug(f"GenAPI._is_finished({task_status})")
        assert (isinstance(task_status, GenAPI.TASK_STATUS))
        if task_status in [GenAPI.TASK_STATUS.generating, GenAPI.TASK_STATUS.waiting, GenAPI.TASK_STATUS.queuing]:
            return False
        return True

    # --- Base Upload & Download Functionality ---

    @handle_http_exceptions
    def upload_file(self, file_path: str | Path) -> str | None:
        """
        Uploads a file via http. Caches upload files to only upload once.
        Args:
            file_path: path to the file to upload

        Returns:
            url of uploaded file
        """
        self._debug(f"{type(self).__name__}.upload_file({file_path}) -- agnostic path")
        local_path = Path(self._path_converter_func(file_path))
        self._debug(f"{type(self).__name__}.upload_file({local_path}) -- local os path")

        if not local_path.exists():
            self._error(f"File not found at path: {local_path}")
            return None

        cache_key = str(local_path.resolve())

        # Subclass-isolated cache lookup
        if cache_key in self.UPLOAD_CACHE:
            self._debug(f"{cache_key} found in cache file URL: {self.UPLOAD_CACHE[cache_key]}")
            return self.UPLOAD_CACHE[cache_key]

        if not self.UPLOAD_URL:
            raise NotImplementedError(f"Subclass '{type(self).__name__}' must define 'UPLOAD_URL'.")

        if not self.JSON_HEADER:
            raise NotImplementedError(f"Subclass '{type(self).__name__}' must define 'JSON_HEADER'.")

        self._info(f"Preparing to upload '{local_path.name}'...")

        # Using context manager to guarantee resource closure
        with open(local_path, 'rb') as f:
            files = {
                'file': (local_path.name, f),
                'uploadPath': (None, 'images/user-uploads'),
                'fileName': (None, local_path.name)
            }
            response = requests.post(self.UPLOAD_URL, headers=self.HEADER, files=files)

        response.raise_for_status()

        # TODO: this response check looks kie.ai specific
        if self._check_api_response(response):
            response_data = response.json().get("data", {})
            file_url = response_data.get("downloadUrl")
            if file_url:
                self._debug(f"File URL: {file_url}")
                self.UPLOAD_CACHE[cache_key] = file_url
                return file_url
            self._error("URL not found in API response.")
        return None

    def upload_files(self, files: list | str | Path) -> list[str | None]:
        """
        Upload a list of files.
        Args:
            files: list of file paths

        Returns:
            list of urls of uploaded files
        """
        self._debug(f"{type(self).__name__}.upload_files({files})")
        if not isinstance(files, list):
            files = [files]
        return [self.upload_file(f) for f in files]

    @handle_http_exceptions
    def download_file(self, url: str, output_path: str | Path) -> int:
        """
        Download a file via http.
        Args:
            url: url of the file to download
            output_path: path to save the downloaded file

        Returns:
            size of downloaded file in bytes
        """
        output_path = Path(output_path)
        self._debug(f"{type(self).__name__}.download_file(url={url}, output_path={output_path})")
        try:
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                total_size = int(r.headers.get('content-length', -1))
                bytes_downloaded = 0
                with open(output_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
                        done = int(50 * bytes_downloaded / total_size) if total_size else 0
                        sys.stdout.write(
                            f"\r  [{'=' * done}{' ' * (50 - done)}] {bytes_downloaded / 1024 / 1024:.2f} MB")
                        sys.stdout.flush()
            sys.stdout.write("\n")

            # Verify actual downloaded bytes match the Content-Length header (if provided)
            if total_size < 0 or bytes_downloaded != total_size:
                raise ValueError(
                    f"Size mismatch for {output_path.name}: expected {total_size} bytes, got {bytes_downloaded} bytes"
                )

            self._debug(f"File saved successfully to: {output_path}")
            return bytes_downloaded

        except (requests.exceptions.RequestException, ValueError) as e:
            sys.stdout.write("\n")
            self._error(f"Failed to download file: {e}")
            raise
