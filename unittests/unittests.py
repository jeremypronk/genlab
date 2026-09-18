import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path, WindowsPath, PosixPath
import os
import shutil
import tempfile
import yaml
import requests
import logging

from genlab import NetworkPathConverter, YamlParamReplacer, setup_logging
from genlab import GenAPI


class TestLoggingSetup(unittest.TestCase):
    def tearDown(self):
        # Close file handles and clear handlers to release Windows file locks
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            handler.close()
            root_logger.removeHandler(handler)

    def test_console_level_toggle(self):
        logger = setup_logging(debug=True, log_file=None)
        console_handler = logger.handlers[0]
        self.assertEqual(console_handler.level, logging.DEBUG)

    def test_file_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test.log"
            logger = setup_logging(debug=False, log_file=log_path)

            logger.info("Unit test entry")

            self.assertTrue(log_path.exists())
            self.assertIn("Unit test entry", log_path.read_text())

            # Close file handlers before context manager attempts cleanup
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)

class BaseTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.logger = setup_logging(debug=True)
        cls.logger.setLevel(logging.DEBUG)

    def run(self, result=None):
        test_id = self.id()
        self.logger.info(f"=== START TEST: {test_id} ===")

        if result is None:
            result = self.defaultTestResult()

        # Track outcome counts before running the test method
        errors_before = len(result.errors)
        failures_before = len(result.failures)
        skips_before = len(getattr(result, 'skipped', []))

        # Execute the actual test method
        super().run(result)

        # Determine outcome by checking changes in test result counts
        if len(result.errors) > errors_before:
            status = "ERROR"
        elif len(result.failures) > failures_before:
            status = "FAILED"
        elif len(getattr(result, 'skipped', [])) > skips_before:
            status = "SKIPPED"
        else:
            status = "PASSED"

        self.logger.info(f"=== END TEST: {test_id} [{status}] ===")
        return result

class TestNetworkPathConverter(BaseTestCase):
    def setUp(self):
        self.mappings = [
            {"win": "P:", "osx": "/Volumes/work"},
            {"win": r"\\Server\Assets", "osx": "/Volumes/Assets"},
            {"win": r"P:\Projects\Special", "osx": "/Volumes/Special"},
            {"win": r"X:", "osx": "/Volumes/projects"}
        ]
        self.converter = NetworkPathConverter(self.mappings)

    def test_win_to_osx(self):
        path = r"P:\Shot_01\render.exr"
        result = self.converter.convert(path, force_os='posix')
        self.assertEqual(result, "/Volumes/work/Shot_01/render.exr")

    def test_osx_to_win(self):
        path = "/Volumes/work/Shot_01/render.exr"
        result = self.converter.convert(path, force_os='nt')
        # This will now correctly match P:\Shot_01\render.exr
        self.assertEqual(result, r"P:\Shot_01\render.exr")

    def test_unc_to_osx(self):
        path = r"\\Server\Assets\Textures\Brick.jpg"
        result = self.converter.convert(path, force_os='posix')
        self.assertEqual(result, "/Volumes/Assets/Textures/Brick.jpg")

    def test_priority_mapping(self):
        r"""Ensures P:\Proj\Special uses the specific mapping, not the P: mapping."""
        path = r"P:\Projects\Special\file.txt"
        result = self.converter.convert(path, force_os='posix')
        self.assertEqual(result, "/Volumes/Special/file.txt")

    def test_normalization_only(self):
        path = "C:/Local/Path\\File.txt"
        result = self.converter.convert(path, force_os='nt')
        self.assertEqual(result, r"C:\Local\Path\File.txt")

    def test_rally(self):
        path = "/Volumes/projects/urf_teaser2/shots/end/end_0020/startframe_outputs/urf_end_0020_v015/urf_end_0020_v015.00006_00001_.png"
        result = self.converter.convert(path, force_os='nt')
        self.assertEqual(result, r"X:\urf_teaser2\shots\end\end_0020\startframe_outputs\urf_end_0020_v015\urf_end_0020_v015.00006_00001_.png")

    def test_rally2(self):
        path = r"X:\urf_teaser2\shots\end\end_0020\startframe_outputs\urf_end_0020_v015\urf_end_0020_v015.00006_00001_.png"
        result = self.converter.convert(path, force_os='posix')
        self.assertEqual(result, r"/Volumes/projects/urf_teaser2/shots/end/end_0020/startframe_outputs/urf_end_0020_v015/urf_end_0020_v015.00006_00001_.png")

    def test_matching_os(self):
        path = r"X:\urf_teaser2\tools\genlab\tester_kling.yaml"
        result = self.converter.convert(path, force_os='nt')
        self.assertEqual(result, r"X:\urf_teaser2\tools\genlab\tester_kling.yaml")
        path = r"/Volumes/projects/urf_teaser2/shots/end/end_0020/startframe_outputs/urf_end_0020_v015/urf_end_0020_v015.00006_00001_.png"
        result = self.converter.convert(path, force_os='osx')
        self.assertEqual(result, r"/Volumes/projects/urf_teaser2/shots/end/end_0020/startframe_outputs/urf_end_0020_v015/urf_end_0020_v015.00006_00001_.png")

    def test_string_input(self):
        path = r"P:\render.exr"
        result = self.converter.convert(path, force_os='posix')
        self.assertIsInstance(result, str)
        self.assertEqual(result, "/Volumes/work/render.exr")

    def test_pathlib_input(self):
        """Tests that passing a Path object returns a Path object."""
        path = Path("/Volumes/work/scene.ma")
        result = self.converter.convert(path, force_os='nt')
        self.assertTrue(isinstance(result, Path))
        # Check string representation for Windows style
        self.assertEqual(str(result).replace('/', '\\'), r"P:\scene.ma")

    def test_bytes_input(self):
        """Tests that passing bytes returns bytes."""
        path = b"P:\\textures\\dirt.dds"
        result = self.converter.convert(path, force_os='posix')
        self.assertIsInstance(result, bytes)
        self.assertEqual(result, b"/Volumes/work/textures/dirt.dds")

    def test_drive_rooting_logic(self):
        """Ensures P: becomes P:\\ and not P:folder."""
        path = "/Volumes/work/shot.mov"
        result = self.converter.convert(path, force_os='nt')
        self.assertEqual(result, r"P:\shot.mov")

    def test_none_input(self):
        self.assertIsNone(self.converter.convert(None))



# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def write_yaml(directory: str, filename: str, data: object) -> str:
    """Serialise *data* as YAML into *directory/filename* and return the path."""
    path = os.path.join(directory, filename)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.dump(data, fh)
    return path

class _TempDirMixin(BaseTestCase):
    """Mixin that provides a fresh temporary directory for each test."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def make_replacer(self, params: dict) -> YamlParamReplacer:
        """Write *params* to a temp YAML file and return a replacer for it."""
        path = write_yaml(self._tmp, "params.yaml", params)
        return YamlParamReplacer(path)

    def write_yaml(self, filename: str, data: object) -> str:
        return write_yaml(self._tmp, filename, data)


# ===========================================================================
# 1. Constructor / initialisation
# ===========================================================================

class TestInit(_TempDirMixin):
    """Tests that cover __init__ validation and state setup."""

    def test_loads_valid_params_file(self):
        replacer = self.make_replacer({"host": "localhost", "port": 5432})
        self.assertEqual(replacer.get_params(), {"host": "localhost", "port": "5432"})

    def test_raises_file_not_found_for_missing_params(self):
        missing = os.path.join(self._tmp, "nonexistent.yaml")
        with self.assertRaises(FileNotFoundError) as ctx:
            YamlParamReplacer(missing)
        self.assertIn("Params file not found", str(ctx.exception))

    def test_raises_value_error_on_empty_params_file(self):
        path = os.path.join(self._tmp, "empty.yaml")
        open(path, "w").close()  # create an empty file
        with self.assertRaises(ValueError) as ctx:
            YamlParamReplacer(path)
        self.assertIn("empty", str(ctx.exception))

    def test_raises_value_error_when_params_file_is_a_list(self):
        path = self.write_yaml("list.yaml", ["item1", "item2"])
        with self.assertRaises(ValueError) as ctx:
            YamlParamReplacer(path)
        self.assertIn("mapping", str(ctx.exception))

    def test_all_param_values_coerced_to_strings(self):
        replacer = self.make_replacer({"int_val": 42, "bool_val": True, "float_val": 3.14})
        params = replacer.get_params()
        self.assertEqual(params["int_val"], "42")
        self.assertEqual(params["float_val"], "3.14")
        # yaml.dump serialises True as 'true'; str(True) gives 'True' — either is fine
        self.assertIsInstance(params["bool_val"], str)

    def test_get_params_returns_independent_copy(self):
        """Mutating the returned dict must not affect the internal state."""
        replacer = self.make_replacer({"key": "original"})
        copy = replacer.get_params()
        copy["key"] = "mutated"
        self.assertEqual(replacer.get_params()["key"], "original")


# ===========================================================================
# 2. Simple / flat token replacement
# ===========================================================================

class TestReplaceTokensSimple(_TempDirMixin):
    """Tests for basic single-level token substitution."""

    def test_single_token_replaced(self):
        replacer = self.make_replacer({"env": "production"})
        self.assertEqual(
            replacer.replace_tokens({"environment": "{{ env }}"}),
            {"environment": "production"},
        )

    def test_multiple_distinct_tokens_in_one_value(self):
        replacer = self.make_replacer({"host": "db.example.com", "port": "5432"})
        result = replacer.replace_tokens({"dsn": "{{ host }}:{{ port }}"})
        self.assertEqual(result, {"dsn": "db.example.com:5432"})

    def test_token_embedded_within_larger_string(self):
        replacer = self.make_replacer({"name": "world"})
        result = replacer.replace_tokens({"greeting": "Hello, {{ name }}!"})
        self.assertEqual(result, {"greeting": "Hello, world!"})

    def test_value_without_tokens_is_unchanged(self):
        replacer = self.make_replacer({"key": "value"})
        result = replacer.replace_tokens({"plain": "no tokens here"})
        self.assertEqual(result, {"plain": "no tokens here"})

    def test_unknown_token_is_left_unchanged(self):
        replacer = self.make_replacer({"known": "ok"})
        result = replacer.replace_tokens({"field": "{{ unknown }}"})
        self.assertEqual(result, {"field": "{{ unknown }}"})

    def test_token_with_surrounding_whitespace(self):
        replacer = self.make_replacer({"key": "value"})
        result = replacer.replace_tokens({"field": "{{  key  }}"})
        self.assertEqual(result, {"field": "value"})

    def test_repeated_token_in_one_value(self):
        replacer = self.make_replacer({"sep": "-"})
        result = replacer.replace_tokens({"val": "{{ sep }}{{ sep }}{{ sep }}"})
        self.assertEqual(result, {"val": "---"})

    def test_known_and_unknown_tokens_in_same_string(self):
        """Known tokens replaced; unknown tokens preserved."""
        replacer = self.make_replacer({"known": "X"})
        result = replacer.replace_tokens({"val": "{{ known }}-{{ unknown }}"})
        self.assertEqual(result, {"val": "X-{{ unknown }}"})


# ===========================================================================
# 3. Type coercion
# ===========================================================================

class TestTypeCoercion(_TempDirMixin):
    """Whole-token strings should be coerced to native Python types."""

    def test_integer_coercion(self):
        replacer = self.make_replacer({"port": 8080})
        result = replacer.replace_tokens({"port": "{{ port }}"})
        self.assertIsInstance(result["port"], int)
        self.assertEqual(result["port"], 8080)

    def test_float_coercion(self):
        replacer = self.make_replacer({"ratio": 0.75})
        result = replacer.replace_tokens({"ratio": "{{ ratio }}"})
        self.assertIsInstance(result["ratio"], float)
        self.assertAlmostEqual(result["ratio"], 0.75)

    def test_bool_true_coercion(self):
        replacer = self.make_replacer({"debug": "true"})
        result = replacer.replace_tokens({"debug": "{{ debug }}"})
        self.assertIs(result["debug"], True)

    def test_bool_false_coercion(self):
        replacer = self.make_replacer({"verbose": "false"})
        result = replacer.replace_tokens({"verbose": "{{ verbose }}"})
        self.assertIs(result["verbose"], False)

    def test_bool_yes_coercion(self):
        replacer = self.make_replacer({"flag": "yes"})
        result = replacer.replace_tokens({"flag": "{{ flag }}"})
        self.assertIs(result["flag"], True)

    def test_bool_no_coercion(self):
        replacer = self.make_replacer({"flag": "no"})
        result = replacer.replace_tokens({"flag": "{{ flag }}"})
        self.assertIs(result["flag"], False)

    def test_no_coercion_when_token_is_in_mixed_string(self):
        """A token embedded in a larger string must NOT trigger type coercion."""
        replacer = self.make_replacer({"port": 8080})
        result = replacer.replace_tokens({"url": "http://localhost:{{ port }}/api"})
        self.assertEqual(result["url"], "http://localhost:8080/api")
        self.assertIsInstance(result["url"], str)

    def test_plain_string_value_stays_string(self):
        replacer = self.make_replacer({"name": "Alice"})
        result = replacer.replace_tokens({"name": "{{ name }}"})
        self.assertIsInstance(result["name"], str)
        self.assertEqual(result["name"], "Alice")


# ===========================================================================
# 4. Recursive / nested structures
# ===========================================================================

class TestRecursiveStructures(_TempDirMixin):
    """Token replacement must recurse into nested dicts and lists."""

    def test_nested_dict(self):
        replacer = self.make_replacer({"host": "localhost", "port": 5432})
        result = replacer.replace_tokens({"db": {"host": "{{ host }}", "port": "{{ port }}"}})
        self.assertEqual(result, {"db": {"host": "localhost", "port": 5432}})

    def test_list_of_strings(self):
        replacer = self.make_replacer({"item": "replaced"})
        result = replacer.replace_tokens(["{{ item }}", "static", "{{ item }}"])
        self.assertEqual(result, ["replaced", "static", "replaced"])

    def test_list_inside_dict(self):
        replacer = self.make_replacer({"tag": "v1.0"})
        result = replacer.replace_tokens({"releases": ["{{ tag }}", "v0.9"]})
        self.assertEqual(result, {"releases": ["v1.0", "v0.9"]})

    def test_deeply_nested_dict(self):
        replacer = self.make_replacer({"secret": "s3cr3t"})
        target = {"a": {"b": {"c": {"d": "{{ secret }}"}}}}
        self.assertEqual(replacer.replace_tokens(target)["a"]["b"]["c"]["d"], "s3cr3t")

    def test_mixed_list_containing_dicts_and_lists(self):
        replacer = self.make_replacer({"env": "prod"})
        target = [{"env": "{{ env }}"}, "static", ["{{ env }}"]]
        self.assertEqual(replacer.replace_tokens(target), [{"env": "prod"}, "static", ["prod"]])


# ===========================================================================
# 5. Non-string scalar pass-through
# ===========================================================================

class TestScalarPassThrough(_TempDirMixin):
    """Native scalars already in the target YAML must pass through untouched."""

    def test_integer_scalar_untouched(self):
        replacer = self.make_replacer({"key": "val"})
        self.assertEqual(replacer.replace_tokens({"count": 42}), {"count": 42})

    def test_float_scalar_untouched(self):
        replacer = self.make_replacer({"key": "val"})
        self.assertEqual(replacer.replace_tokens({"ratio": 1.5}), {"ratio": 1.5})

    def test_bool_scalar_untouched(self):
        replacer = self.make_replacer({"key": "val"})
        self.assertIs(replacer.replace_tokens({"flag": True})["flag"], True)

    def test_none_scalar_untouched(self):
        replacer = self.make_replacer({"key": "val"})
        self.assertIsNone(replacer.replace_tokens({"nothing": None})["nothing"])


# ===========================================================================
# 6. replace_tokens_from_file
# ===========================================================================

class TestReplaceTokensFromFile(_TempDirMixin):
    """Tests for the file-based convenience method."""

    def test_replaces_tokens_loaded_from_target_file(self):
        replacer = self.make_replacer({"greeting": "Hello", "name": "World"})
        target_path = self.write_yaml("target.yaml", {"message": "{{ greeting }}, {{ name }}!"})
        result = replacer.replace_tokens_from_file(target_path)
        self.assertEqual(result, {"message": "Hello, World!"})

    def test_raises_file_not_found_for_missing_target(self):
        replacer = self.make_replacer({"key": "val"})
        with self.assertRaises(FileNotFoundError) as ctx:
            replacer.replace_tokens_from_file(os.path.join(self._tmp, "missing.yaml"))
        self.assertIn("Target file not found", str(ctx.exception))

    def test_nested_target_file_processed_correctly(self):
        replacer = self.make_replacer({"region": "us-east-1", "tier": "premium"})
        target_path = self.write_yaml(
            "target.yaml",
            {"cloud": {"region": "{{ region }}", "tier": "{{ tier }}"}},
        )
        result = replacer.replace_tokens_from_file(target_path)
        self.assertEqual(result, {"cloud": {"region": "us-east-1", "tier": "premium"}})


# ===========================================================================
# 7. Edge cases
# ===========================================================================

class TestEdgeCases(_TempDirMixin):
    """Boundary and defensive-programming scenarios."""

    def test_empty_dict_target_returns_empty_dict(self):
        replacer = self.make_replacer({"key": "val"})
        self.assertEqual(replacer.replace_tokens({}), {})

    def test_empty_list_target_returns_empty_list(self):
        replacer = self.make_replacer({"key": "val"})
        self.assertEqual(replacer.replace_tokens([]), [])

    def test_target_with_no_tokens_is_structurally_identical(self):
        replacer = self.make_replacer({"key": "val"})
        target = {"a": 1, "b": "plain", "c": [True, None]}
        self.assertEqual(replacer.replace_tokens(target), target)

    def test_original_dict_target_is_not_mutated(self):
        replacer = self.make_replacer({"env": "prod"})
        original = {"env": "{{ env }}"}
        replacer.replace_tokens(original)
        self.assertEqual(original, {"env": "{{ env }}"})

    def test_original_list_target_is_not_mutated(self):
        replacer = self.make_replacer({"x": "1"})
        original = ["{{ x }}"]
        replacer.replace_tokens(original)
        self.assertEqual(original, ["{{ x }}"])

    def test_param_value_containing_special_url_characters(self):
        replacer = self.make_replacer({"url": "https://example.com/path?q=1&r=2"})
        result = replacer.replace_tokens({"endpoint": "{{ url }}"})
        self.assertEqual(result["endpoint"], "https://example.com/path?q=1&r=2")

    def test_large_param_set_all_replaced(self):
        params = {f"key{i}": f"val{i}" for i in range(20)}
        replacer = self.make_replacer(params)
        target = {f"field{i}": "{{{{ key{i} }}}}".format(i=i) for i in range(20)}
        result = replacer.replace_tokens(target)
        for i in range(20):
            self.assertEqual(result[f"field{i}"], f"val{i}")

class TestInlineYamlStrings(_TempDirMixin):
    """
    End-to-end tests driven entirely by inline YAML strings.

    Each test defines three YAML documents as triple-quoted strings:
      - PARAMS_YAML  — the parameter name/value pairs (written to a temp file
                       so YamlParamReplacer can load it normally)
      - TARGET_YAML  — the template to process, passed as a loaded object
      - EXPECTED_YAML — the anticipated result after substitution

    This style mirrors real-world usage where both files exist on disk and
    makes the intent of each test immediately readable.
    """

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _make_replacer_from_string(self, params_yaml: str) -> YamlParamReplacer:
        """Write an inline YAML string to a temp file and return a replacer."""
        path = os.path.join(self._tmp, "params.yaml")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(params_yaml)
        return YamlParamReplacer(path)

    def test_genlab_style_replace(self):
        params_yaml = """
images: /Volumes/projects/urf_teaser2/shots/end/end_0020/startframe_outputs/urf_end_0020_v015/urf_end_0020_v015.00006_00001_.png
prompt: A realistic wide angle dolly shot moving slowly forward through a forest of tall Corsican pine trees that are swaying and jostling in the breeze. Down near the forest floor there is a light mist catching slithers of light that reach down from the overcast sky above the high canopy of the forest. Shot on 28mm wide-angle lens, f/11 with deep focus, natural lighting, high-resolution photography.
"""
        target_yaml = """
model: kling-3.0/video
images: "{{ images }}"
prompt: "{{ prompt }}"
sound: false
multi_shots: false
kling_elements: []
duration: 5
mode: pro
"""
        expected_yaml = """
model: kling-3.0/video
images: /Volumes/projects/urf_teaser2/shots/end/end_0020/startframe_outputs/urf_end_0020_v015/urf_end_0020_v015.00006_00001_.png
prompt: A realistic wide angle dolly shot moving slowly forward through a forest of tall Corsican pine trees that are swaying and jostling in the breeze. Down near the forest floor there is a light mist catching slithers of light that reach down from the overcast sky above the high canopy of the forest. Shot on 28mm wide-angle lens, f/11 with deep focus, natural lighting, high-resolution photography.
sound: false
multi_shots: false
kling_elements: []
duration: 5
mode: pro
"""
        replacer = self._make_replacer_from_string(params_yaml)
        result   = replacer.replace_tokens(yaml.safe_load(target_yaml))
        expected = yaml.safe_load(expected_yaml)
        self.assertEqual(result, expected)
        # # Also verify the native types survive the round-trip
        # self.assertIsInstance(result["config"]["workers"], int)
        # self.assertIsInstance(result["config"]["rate"], float)
        # self.assertIs(result["config"]["verbose"], True)



class TestGenAPI(BaseTestCase):
    def setUp(self):
        # Create concrete subclasses specifically for testing base class mechanics
        class SubAPI1(GenAPI):
            UPLOAD_URL = "https://api1.test/upload"

        class SubAPI2(GenAPI):
            UPLOAD_URL = "https://api2.test/upload"

        self.SubAPI1 = SubAPI1
        self.SubAPI2 = SubAPI2

        # Temporary workspace directory
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)

        # Create sample dummy file
        self.test_file = self.workspace / "sample.png"
        self.test_file.write_bytes(b"dummy image contents")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_subclass_cache_isolation(self):
        """Verify each subclass gets its own distinct UPLOAD_CACHE dictionary."""
        api1 = self.SubAPI1(self.workspace)
        api2 = self.SubAPI2(self.workspace)

        api1.UPLOAD_CACHE["dummy_key"] = "https://cdn.test/1.png"

        self.assertIn("dummy_key", api1.UPLOAD_CACHE)
        self.assertNotIn("dummy_key", api2.UPLOAD_CACHE)
        self.assertIsNot(api1.UPLOAD_CACHE, api2.UPLOAD_CACHE)

    @patch("requests.post")
    def test_upload_file_network_and_caching(self, mock_post):
        """Verify network call occurs once and subsequent requests hit the subclass cache."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 200,
            "data": {"downloadUrl": "https://cdn.test/uploaded.png"}
        }
        mock_post.return_value = mock_response

        api = self.SubAPI1(self.workspace)

        # First call: triggers HTTP POST request
        url1 = api.upload_file(self.test_file)
        self.assertEqual(url1, "https://cdn.test/uploaded.png")
        self.assertEqual(mock_post.call_count, 1)

        # Second call: should hit cache without issuing new POST request
        url2 = api.upload_file(self.test_file)
        self.assertEqual(url2, "https://cdn.test/uploaded.png")
        self.assertEqual(mock_post.call_count, 1)

    def test_upload_file_nonexistent_path(self):
        """Verify uploading a missing file returns None without calling network."""
        api = self.SubAPI1(self.workspace)
        missing_file = self.workspace / "missing.jpg"

        result = api.upload_file(missing_file)
        self.assertIsNone(result)

    @patch("requests.post")
    def test_upload_file_api_error_code(self, mock_post):
        """Verify failing API status response returns None."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"code": 400, "msg": "Bad request"}
        mock_post.return_value = mock_response

        api = self.SubAPI1(self.workspace)
        result = api.upload_file(self.test_file)

        self.assertIsNone(result)

    @patch("requests.post")
    def test_upload_files_batch(self, mock_post):
        """Verify batch list uploads process correctly."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 200,
            "data": {"downloadUrl": "https://cdn.test/uploaded.png"}
        }
        mock_post.return_value = mock_response

        api = self.SubAPI1(self.workspace)
        urls = api.upload_files([self.test_file])

        self.assertEqual(urls, ["https://cdn.test/uploaded.png"])

    @patch("requests.get")
    def test_download_file_success(self, mock_get):
        """Verify file stream download writes bytes correctly and returns total byte count."""
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "12"}
        mock_response.iter_content.return_value = [b"chunk1", b"chunk2"]
        mock_response.__enter__.return_value = mock_response
        mock_get.return_value = mock_response

        api = self.SubAPI1(self.workspace)
        destination = self.workspace / "downloaded.png"

        # 1. Capture the return value
        downloaded_size = api.download_file("https://cdn.test/source.png", destination)

        # 2. Verify requests.get call parameters (e.g., stream=True)
        mock_get.assert_called_once_with("https://cdn.test/source.png", stream=True)

        # 3. Assert return value matches content length
        self.assertEqual(downloaded_size, 12)

        # 4. Verify disk payload
        self.assertTrue(destination.exists())
        self.assertEqual(destination.read_bytes(), b"chunk1chunk2")

    @patch("requests.get")
    def test_download_file_zero_content_length(self, mock_get):
        """Verify behavior when response header reports zero content length."""
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "0"}
        mock_response.iter_content.return_value = []
        mock_response.__enter__.return_value = mock_response
        mock_get.return_value = mock_response

        api = self.SubAPI1(self.workspace)
        destination = self.workspace / "empty.png"

        downloaded_size = api.download_file("https://cdn.test/source.png", destination)

        self.assertEqual(downloaded_size, 0)
        self.assertEqual(destination.read_bytes(), b"")
