import os
import posixpath
import ntpath
from pathlib import Path
import re
import yaml


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