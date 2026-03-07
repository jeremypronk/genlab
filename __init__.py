import os
import posixpath
import ntpath
from pathlib import Path


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