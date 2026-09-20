import os
import requests
import json
from pathlib import Path

from . import GenAPI
from . import handle_http_exceptions, get_safe_filename


class KieAIGen(GenAPI):
    """
    Base class for kie.ai API

    You can pass your api key in the environment variable KIE_API_KEY or to the class constructor
    """
    API_SERVER = "https://api.kie.ai"
    BASE_API_URL = f"{API_SERVER}/api/v1"
    CREATE_TASK_URL = f"{BASE_API_URL}/jobs/createTask"
    QUERY_TASK_URL = f"{BASE_API_URL}/jobs/recordInfo"
    UPLOAD_URL = "https://kieai.redpandaai.co/api/file-stream-upload"
    API_KEY = None

    PLATFORM = "kieai"

    def __init__(self, output_basepath, api_key=None, path_converter_func=lambda x: x):
        super().__init__(output_basepath, path_converter_func=path_converter_func)
        if not api_key:
            try:
                KieAIGen.API_KEY = os.environ["KIE_API_KEY"]
            except KeyError:
                self._error("FATAL: KIE_API_KEY environment variable is not set.")
                self._error("Please set your API key, e.g., 'export KIE_API_KEY=\"your_key\"'")
                sys.exit(-50)
            self._info("kie.ai api key found in environment variable KIE_API_KEY")
        else:
            self._info("kie.ai api key passed in constructor")
            KieAIGen.API_KEY = api_key
            
        self.HEADER = {"Authorization": f"Bearer {KieAIGen.API_KEY}"}
        self.JSON_HEADER |= self.HEADER

    def _get_task_status(self, query_task_response):
        """
        returns TASK_STATUS for a task query
        """
        self._debug(f"KieAIGen._get_task_status({query_task_response})")
        task_response_status = query_task_response['data']['state']
        if "success" in task_response_status.lower():
            return self.TASK_STATUS.completed
        elif "fail" in task_response_status.lower():
            return self.TASK_STATUS.failed
        elif "gen" in task_response_status.lower():
            return self.TASK_STATUS.generating
        elif "wait" in task_response_status.lower():
            return self.TASK_STATUS.waiting
        elif "que" in task_response_status.lower():
            return self.TASK_STATUS.queuing
        else:
            return self.TASK_STATUS.unknown

    def _attach_metadata(self, file, metadata):
        pass

    def _download(self, query_task_response):
        """
        For details on the contents of the task response see,
        https://docs.kie.ai/market/common/get-task-detail
        Args:
            query_task_response: kie.ai task response
        """
        self._debug(f"KieAIGen._download(query_task_response={query_task_response})")

        urls = json.loads(query_task_response['data']['resultJson'])['resultUrls']
        for url in urls:
            name = get_safe_filename(url)
            output_path = Path(self._output_basepath).with_suffix(Path(name).suffix)

            self._info(f"Downloading file: {url} --> {output_path}")
            self.download_file(url, output_path)

    def download_result(self):
        self._debug(f"KieAIGen.download_result()")

        (task_status, query_task_response) = self.query_task()
        if task_status == GenAPI.TASK_STATUS.completed:
            self._info("Generation task complete!")
            self._download(query_task_response)

        # generation did not complete...
        elif task_status == None:
            self._error(f"Task state returned None!")
        elif task_status == GenAPI.TASK_STATUS.failed:
            self._error("Attempting to download a failed generation!!")
            self._log_failure_msg(query_task_response)
        elif task_status == GenAPI.TASK_STATUS.unknown:
            self._error(f"Unknown task status!")
        else:
            self._info(f"Task status: {task_status.name}")

        return task_status

    def prep_param(self, param, value) -> tuple:
        """
        kie.ai legacy image payload params are named image_input and video payload image and video reference params
        all end in _url (single ref) or _urls (list of refs).
        Uploads url params if they contain a path to a local file, replacing path value with the new url.
        (upload_file() handles input urls by simple returning the input path)
        Args:
            param task/request parameter
            value task/request value

        Returns:
            tuple of task ready param,value pair.
        """
        if param.endswith('url'):
            value = self.upload_file(value) # returns a string
        elif param.strip().lower() == 'image_input' or param.endswith('urls'):
            value = self.upload_files(value) # returns a list of strings
            if None in value: value = None # fail on any missing input path

        return (param, value)
    
    @handle_http_exceptions
    def prep_task(self, input_payload) -> bool:
        self._debug(f"KieAIGen.prep_task({input_payload})")
        super().prep_task(input_payload=input_payload)

        # build the task payload
        self._payload = dict()
        self._payload['model'] = input_payload['model']
        self._payload['input'] = {}

        # copy relevant param/value pairs
        _exclude_list = ['model']
        for input_param in input_payload:
            if input_param not in _exclude_list:
                param, value = self.prep_param(input_param, input_payload[input_param])
            else:
                self._debug(f"prep_task skip input param: {input_param})")
                continue

            # check the param is value NULL or NONE IS NOT VALID
            if None in (param, value):
                self._error(f"prep_task param/value fail {param}, {value} (input payload {input_param}: {input_payload[input_param]})")
                return False

            # add the param to the task/request payload
            self._payload['input'][param] = value

        return True

    @handle_http_exceptions
    def submit_task(self, test=False) -> str:
        self._debug(f"KieAIGen.submit_task()")
        self._debug(f"task/request payload({self._payload})")

        if super().submit_task(): # check we haven't already sub'd this task/request
            pass # not sure how pythonic this is
        elif test:
            # send back a fake task_id
            import uuid
            self._task_id = uuid.uuid4().hex  # alphanumeric (32 chars)
            self._warning(f"Test mode, created a fake task with id: {self._task_id}")
        else:
            response = requests.post(KieAIGen.CREATE_TASK_URL, json=self._payload, headers=self.JSON_HEADER)
            response.raise_for_status()
            if self._check_api_response(response):
                response_json = response.json()
                self._task_id = response_json['data']['taskId']
            else:
                return None

        return self._task_id

    @handle_http_exceptions
    def query_task(self) -> tuple:
        """
        For details on the contents of the task response see,
        https://docs.kie.ai/market/common/get-task-detail
        """
        self._debug(f"KieAIGen.query_task()")
        response = requests.get(f"{KieAIGen.QUERY_TASK_URL}?taskId={self._task_id}", headers=self.HEADER)
        response.raise_for_status()
        if self._check_api_response(response):
            response_json = response.json()
            return (self._get_task_status(response_json), response_json)
        return (None, None)

