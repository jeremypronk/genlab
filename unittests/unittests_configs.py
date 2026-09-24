import unittest
from pathlib import Path
import yaml
from pprint import pprint

from .unittests import BaseTestCase

from genlab.config import Config

CONFIG_PATH = Path("configs/kieai.yml")


class TestConfigYaml(unittest.TestCase):
    def setUp(self):
        self.text = CONFIG_PATH.read_text(encoding="utf-8")

    def test_yaml_is_valid(self):
        try:
            data = yaml.safe_load(self.text)
        except yaml.YAMLError as e:
            self.fail(f"{CONFIG_PATH.name} is not valid YAML: {e}")

        self.assertIsNotNone(data, "YAML file is empty")
        self.assertIsInstance(data, dict, "Top level should be a mapping")

    def test_no_quotes(self):
        QUOTES = {"'", '"'}

        def find_quoted_keys(node, path=""):
            bad = []
            if isinstance(node, dict):
                for k, v in node.items():
                    p = f"{path}/{k}"
                    if isinstance(k, str) and QUOTES & set(k):
                        bad.append(p)
                    bad += find_quoted_keys(v, p)
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    bad += find_quoted_keys(v, f"{path}[{i}]")
            return bad

        data = yaml.safe_load(self.text)
        self.assertEqual(find_quoted_keys(data), [])

class TestConfigValidation(BaseTestCase):
    def setUp(self):
        self.config = Config()
        self.config._config = {'kieai': {'kling': {'3.0-fflf-std': {'model': 'crower', '$duration': [1,8,512], '^first_frame': "", '^last_frame': "", '?image_urls': ["@first_frame", "@last_frame"]}}}}
    
    def test_configs(self):
        with self.assertRaises(KeyError):
            self.config.build_payload('kieai', 'kling', '3.0-fflf-std', {"prompt": "yada yada yada", "duration": 8, "first_frame": "c:/first.png"}) # missing last_frame

        with self.assertRaises(ValueError):
            self.config.build_payload('kieai', 'kling', '3.0-fflf-std', {"prompt": "yada yada yada", "duration": 4, "first_frame": "c:/first.png", "last_frame": "last.jpg"}) # duration enum invalid

        with self.assertRaises(KeyError):
            self.config.build_payload('topaz', 'kling', '3.0-fflf-std', {"prompt": "yada yada yada", "duration": 8, "first_frame": "c:/first.png", "last_frame": "last.jpg"}) # api type invalid


class TestPayload(BaseTestCase):
    def setUp(self):
        self.config = Config()
        self.config._config = {'kieai': {
            'kling': {'3.0-fflf-std': {'model': 'crower', '$duration': [1, 8, 512], '^first_frame': "", '^last_frame': "", '?image_urls': ["@first_frame", "@last_frame"]}}}}

    def test_payload(self):
        payload_no_extras = self.config.build_payload('kieai', 'kling', '3.0-fflf-std',
                                                      {
                                                          "prompt": "yada yada yada",
                                                          "duration": 8,
                                                          "first_frame": "c:/first.png",
                                                          "last_frame": "last.jpg"}, include_extra_params=False)
        self.assertEqual(payload_no_extras, {'model': 'crower',"duration": 8, "image_urls": ["c:/first.png", "last.jpg"]})
        
        payload = self.config.build_payload('kieai', 'kling', '3.0-fflf-std',
                                                      {
                                                          "prompt": "yada yada yada",
                                                          "duration": 8,
                                                          "first_frame": "c:/first.png",
                                                          "last_frame": "last.jpg"}, include_extra_params=True)
        self.assertEqual(payload, {'model': 'crower',"duration": 8, "image_urls": ["c:/first.png", "last.jpg"], "prompt": "yada yada yada"})


class TestConfigs(BaseTestCase):
    def setUp(self):
        self.config = Config()
        self.config.load("configs")

        # print(self.config)

    def test_kie_kling(self):
        payload = self.config.build_payload('kieai', 'kling', '3.0-fflf-pro',
                                            {"prompt": "into the black", "duration": 4,
                                                          "first_frame": "c:/first.png",
                                                          "last_frame": "last.jpg"}, include_extra_params=False)
        self.assertEqual(payload, {"model": "kling-3.0/video", "duration": 4,
                                   "image_urls": ["c:/first.png", "last.jpg"],
                                   "prompt": "into the black",
                                   "mode": "pro",
                                   "sound": False,
                                   "multi_shots": False})

    def test_kie_seedance(self):
        payload = self.config.build_payload('kieai', 'seedance', '2.0-fast-fflf-480p',
                                            {
                                                "prompt": "into the black",
                                                "duration": 9,
                                                "first_frame": "c:/1.png",
                                                "last_frame": "d:/2.jpg",
                                            }, include_extra_params=False)
        self.assertEqual(payload, {
            "model": "bytedance/seedance-2-fast",
            "duration": 9,
            "first_frame_url": "c:/1.png",
            "last_frame_url": "d:/2.jpg",
            "prompt": "into the black",
            "resolution": "480p",
            "web_search": False,
            "nsfw_checker": False,
            "aspect_ratio": "16:9",
            "generate_audio": False,
        }, )

    def test_nano(self):
        payload = self.config.build_payload('kieai', 'image', 'nano-banana-pro-i2i-2K',
                                            {"prompt": "into the black",
                                                      "image": "c:/first.png"}, include_extra_params=False)
        self.assertEqual(payload, {"model": "nano-banana-pro",
                                   "image_input": "c:/first.png",
                                   "prompt": "into the black",
                                   "aspect_ratio": "auto",
                                   "resolution": "2K",
                                   "output_format": "png"})

    def test_gpt(self):
        payload = self.config.build_payload('kieai', 'gpt-image', '2.5-sunburst-t2i-4K',
                                            {"prompt": "into the black"}, include_extra_params=False)
        self.assertEqual(payload, {"model": "gpt-image-2-5-sunburst-text-to-image",
                                   "prompt": "into the black",
                                   "aspect_ratio": "16:9",
                                   "resolution": "4K",
                                   "background": "auto"})

    def test_configs(self):
        self.assertTrue("kieai" in self.config.apis)
        self.assertTrue("kling" in self.config.types(api='kieai'))
        self.assertTrue("2.5-fflf-720p" in self.config.models(api='kieai', type='seedance'))


if __name__ == "__main__":
    unittest.main()