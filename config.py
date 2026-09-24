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
    # $ (dollar) prepending key is a required param and an enum
    ENUM_ELEMENT_PREFIX     = "$"
    # ? (question) prepending key is a param with referenced values (see REF_VALUE_PREFIX)
    REF_ELEMENT_PREFIX      = "?"
    # @ (at symbol) prepends reference element name
    REF_VALUE_PREFIX        = "@"

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

    @property
    def apis(self) -> list:
        """
        List of all provider APIs currently loaded.
        Returns:
            list of str
        """
        return list(self._config.keys())

    @property
    def all_types(self) -> list:
        """
        List of all types ACROSS ALL APIs currently loaded.
        Returns:
            list of str
        """
        types = set()
        for api in self._config:
            types.update(self._config[api].keys())
        return list(types)

    def types(self, api: str) -> list:
        """
        List of types available for the given api
        Args:
            api:
                API name
        Returns:
            list of str
        """
        return list(self._config[api].keys())

    def models(self, api: str, type: str) -> list:
        """
        List of models available for the given api and type
        Args:
            api:
                API name
                type name
        Returns:
            list of str
        """
        return list(self._config[api][type])

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
            
            # remove default entries
            # (defaults should only be used for template entries)
            for type in self._config[config_name].copy():
                if type.startswith('default'):
                    del(self._config[config_name][type])

        # check the loaded config is valid
        for api in self._config:
            if not self._config[api]:
                raise IndexError(f"(Config.load) config for \"{api}\" empty")
            for type in self._config[api]:
                if not self._config[api][type]:
                    raise IndexError(f"(Config.load) config for \"{api}\" type \"{type}\" empty")
                for model in self._config[api][type]:
                    if not self._config[api][type][model]:
                        raise IndexError(f"(Config.load) config for \"{api}\" type\"{type}\" model \"{model}\" empty")

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
        model_config = copy.deepcopy(self._config[api][type][model]) # make a complete copy to avoid referencing the config db
        for config_param, config_value in model_config.items():

            # handle input params
            if config_param[0] in [Config.REQUIRED_ELEMENT_PREFIX, Config.ENUM_ELEMENT_PREFIX]:
                param = config_param[1:]

                # check required params are preset
                if param not in params:
                    raise KeyError(f"required param {param} is missing")

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


        # handle referenced param values
        for param, value in payload.copy().items():

            # connect reference element
            if param[0] == Config.REF_ELEMENT_PREFIX:
                ref_param = param[1:]
                payload[ref_param] = payload.pop(param) # remove the REF_ELEMENT_PREFIX from the param name

                # if a list need to check each time for reference link
                if isinstance(value, (list, tuple)):
                    for i, v in enumerate(value):
                        if v[0] == Config.REF_VALUE_PREFIX: # is this a referenced value?
                            param_ref = v[1:] # referenced param name
                            payload[ref_param][i] = payload[param_ref] # use the value from the referenced param
                            del(payload[param_ref]) # remove the referenced param

                        else:
                            # just use the value, no reference found
                            payload[ref_param][i] = v

                # is it a reference line ?
                elif isinstance(value, str):
                    if value[0] == Config.REF_VALUE_PREFIX:  # is this a referenced value? (if not there is not point to this)
                        param_ref = value[1:]  # referenced param name
                        payload[ref_param] = payload[param_ref]  # use the value from the referenced param
                        del(payload[param_ref]) # remove the referenced param

                    else:
                        # just use the value, no reference found
                        payload[ref_param] = value


        # find input params that are not listed in the config (not including reference params)
        all_extra_params = list(set(params.keys()) - set(payload.keys()))
        # and remove extras that have been referenced
        extra_params = []
        for extra_param in all_extra_params:
            if f"^{extra_param}" not in self._config[api][type][model]:
                extra_params.append(extra_param)
        # any left?
        if extra_params:

            if include_extra_params:
                logging.info(f"(Config.build_payload) including extra parameters {extra_params} in the payload not present in the config for \"{api} {type} {model}\"")

                payload.update({k: params[k] for k in extra_params if k in params})

            else:
                logging.warning(f"(Config.build_payload) extra parameters {extra_params} are not being added to the payload config for \"{api} {type} {model}\"")

        return payload