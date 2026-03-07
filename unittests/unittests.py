import unittest
from pathlib import Path, WindowsPath, PosixPath
from __init__ import NetworkPathConverter

class TestNetworkPathConverter(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()