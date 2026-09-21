import copy
import logging

import yaml
from pathlib import Path

class Config:
    """
    Configurable interface for gen ai api parameter task/request payloads.

    """

    # template elements are culled (used as references in yaml build)
    TEMPLATE_ELEMENT_PREFIX = ".tmpl."
    # ^ (caret) prepending key is a required param
    REQUIRED_ELEMENT_PREFIX = "^"
    # $ (dollar sing) prepending key is a required param and an enum
    ENUM_ELEMENT_PREFIX     = "$"

    def __init__(self, ):
        self._config = {}

    def __str__(self):
        config_str = ""
        for api in sorted(self._config.keys()):
            config_str += f"{api}\n"

            for type in sorted(self._config[api].keys()):
                config_str += f"\t{type}\n"

                for model in sorted(self._config[api][type].keys()):
                    config_str += f"\t\t{model}\n"
        return config_str

    def load(self, config_path: Path):
        """
        Loads all config yamls found in the provided path.
        Args:
            config_path: path to the config yaml file.

        Returns:
            list of provider apis found and loaded.
        """

        def strip(node, depth, prefix):
            if not isinstance(node, dict):
                return node
            if depth == 0:
                return {k: v for k, v in node.items() if not str(k).startswith(prefix)}
            return {k: strip(v, depth - 1, prefix) for k, v in node.items()}

        self._config = {}
        
        config_files = list(Path(config_path).glob("*.yml"))
        for config_file in config_files:
            config_name = config_file.stem
            logging.info(
                f"(Config.load) loading config for {config_name}")
            config_text = config_file.read_text(encoding="utf-8")
            config_yaml = yaml.safe_load(config_text)
            self._config[config_name] = strip(config_yaml, depth=1, prefix=Config.TEMPLATE_ELEMENT_PREFIX) # remove template entries

        return self._config.keys()

    classmethod
    def get_type(x):
        if isinstance(x, (list, tuple)):
            return f"{type(x).__name__}[{', '.join(Config.get_type(i) for i in x)}]"
        return type(x).__name__

    def build_payload(self, api: str, type: str, model: str, params: dict, include_extra_params=True):
        """
        Build a task/request payload.
        Args:
            api: api provider
            type: model type
            model: model name
            params: input parameters
            include_extra_params: True to include input parameters not listed in the config

        Returns:
            dict task/request payload
        """
        if api not in self._config:
            raise KeyError(f'API "{api}" was not found.')

        if type not in self._config[api]:
            raise KeyError(f'Config of type "{type}" was not found.')

        if model not in self._config[api][type]:
            raise KeyError(f'Model of type "{model}" was not found.')

        # build the payload
        payload = {}
        for config_param, config_value in self._config[api][type][model].items():

            # handle input params
            if config_param[0] in [Config.REQUIRED_ELEMENT_PREFIX, Config.ENUM_ELEMENT_PREFIX]:
                param = config_param[1:]

                # check required params are preset
                if param not in params:
                    raise ValueError(f"required param {param} is missing")

                # check enum params are valid
                if config_param[0] == Config.ENUM_ELEMENT_PREFIX and params[param] not in config_value:
                    raise ValueError(f"param {param} has an invalid value {params[param]} for ENUM{config_value}")

                # check required params have the correct value types
                elif config_param[0] == Config.REQUIRED_ELEMENT_PREFIX:
                    required_type = Config.get_type(config_value)
                    param_type = Config.get_type(params[param])
                    if param_type != required_type:
                        raise ValueError(
                            f"param {param} has an invalid value, got {params[param]} expected {required_type}")

                # copy in the param,value
                payload[param] = params[param]

            else:

                # use the config setting
                payload[config_param] = config_value


        # find input params that are not listed in the config
        extra_params = list(set(params.keys()) - set(payload.keys()))
        if extra_params:

            if include_extra_params:
                logging.info(f"(Config.build_payload) including extra parameters {extra_params} in the payload not present in the config for \"{api} {type} {model}\"")

                payload.update({k: params[k] for k in extra_params if k in params})

            else:
                logging.warning(f"(Config.build_payload) extra parameters {extra_params} are not being added to the payload config for \"{api} {type} {model}\"")

        return payload