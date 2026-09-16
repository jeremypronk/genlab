import requests
import yaml
import json
import os
import time
import logging
import sys
import functools
import argparse
import re
import glob
from pathlib import Path
from enum import Enum

from . import NetworkPathConverter
from . import YamlParamReplacer

_API_KEY = None
_TASKS_WAITING_QUEUE = []

_CONFIG_FILENAME = r'config.yaml'

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
    
class GenAPI:
    
    class TASK_STATUS(Enum):
        completed = 1
        failed = 2
        generating = 3
        waiting = 4
        queuing = 5
        unknown = 6
    
class KieAIGen(GenAPI):
    """
    Base class for kie.ai api
    """
    API_SERVER = "https://api.kie.ai"
    BASE_API_URL = f"{API_SERVER}/api/v1"
    CREATE_TASK_URL = f"{BASE_API_URL}/jobs/createTask"
    QUERY_TASK_URL = f"{BASE_API_URL}/jobs/recordInfo"
    UPLOAD_URL = "https://kieai.redpandaai.co/api/file-stream-upload"

    # upload cache is shared across all instances of kie ai gen subclasses
    UPLOAD_CACHE = {} 
    
    def __init__(self, api_key, output_basepath, task_id=None, path_converter_func=lambda x: x):
        logging.debug(f"KieAIGen(api_key={api_key}, task_id={task_id})")
        super().__init__()
        
        self._api_key = api_key
        
        self._output_basepath = Path(output_basepath)
        self._task_id = task_id
        self._auth_header = {
            "Authorization": f"Bearer {self._api_key}",
        }
        self._json_header = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }
        self._path_converter_func = path_converter_func

class KieAIVideoGen(KieAIGen):
    """
    Base class for kie.ai video gen api
    """

    def __init__(self, api_key, output_basepath, task_id=None, path_converter_func=lambda x: x):
        logging.debug(f"KieAIVideoGen(api_key={api_key}, task_id={task_id})")
        super().__init__(api_key, output_basepath, task_id, path_converter_func))

    def __repr__(self):
        return f"KieAIVideoGen({self._task_id}, {self._output_basepath})"

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
        self._debug(f"KieAIVideoGen._check_api_response({response})")
        response_json = response.json()
        if response_json['code'] == 200:
            self._debug(f"Request was successful.")
        # elif response_json['code'] == 400:
        #     self._error(f"Content violation error, check your prompt and/or input images for content that violates the T&Cs.")
        #     return False
        # elif response_json['code'] == 401:
        #     self._error(f"Unauthorized - Authentication credentials are missing or invalid.")
        #     return False
        # elif response_json['code'] == 402:
        #     self._error(f"Insufficient Credits - Account does not have enough credits to perform the operation.")
        #     return False
        else:
            if 'msg' in response_json:
                self._error(f"Error: API response code:- {response_json['code']} API response msg:- {response_json['msg']}")
            else:
                self._error(f"Unknown error ({response_json})")
            return False
        return True

    @handle_http_exceptions
    def upload_file(self, file_path: str) -> str | None:
        self._debug(f"KieAIVideoGen.upload_file({file_path}) -- agnostic path")
        file_path = self._path_converter_func(file_path)
        self._debug(f"KieAIVideoGen.upload_file({file_path}) -- local os path")
        if not os.path.exists(file_path):
            self._error(f"File not found at path: {file_path}")
            return None

        if file_path in self._upload_cache:
            self._debug(f"{file_path} found in cache file URL: {self._upload_cache[file_path]}")
            return self._upload_cache[file_path]

        files = {
            'file': (os.path.basename(file_path), open(file_path, 'rb')),
            'uploadPath': (None, 'images/user-uploads'),
            'fileName': (None, os.path.basename(file_path))
        }
        self._info(f"Preparing to upload '{files}'...")
        response = requests.post(KieAIVideoGen._upload_url, headers=self._auth_header, files=files)
        response.raise_for_status()
        if self._check_api_response(response):
            response_data = response.json()["data"]

            # Extract the URL from the JSON response.
            file_url = response_data.get("downloadUrl")
            if file_url:
                self._debug(f"File URL: {file_url}")
                KieAIVideoGen._upload_cache[file_path] = file_url
                return self._upload_cache[file_path]
            else:
                self._error("URL not found in API response.")
        return None

    def upload_files(self, files):
        self._debug(f"KieAIVideoGen.upload_files({files})")
        # upload files and return urls to uploaded files
        file_urls = list()
        if not isinstance(files, list):
            files = [files]
        for file in files:
            file_urls.append(self.upload_file(file))
        return file_urls

    @handle_http_exceptions
    def create_task(self, payload, test=False):
        """
        any field names ending with url or urls are assumed to point to local files that will be uploaded
        """
        self._debug(f"KieAIVideoGen.create_task({payload})")

        # build the task payload
        task_payload = dict()
        task_payload['model'] = payload['model']
        task_payload['input'] = {}

        # copy relevant keys
        # upload any files in url keys
        # TODO: should check if it is already a url then no need to upload just skip
        _exclude_list = ['model']
        for key in payload:
            if key.endswith('url'):
                task_payload['input'][key] = self.upload_file(payload[key])
            elif key.endswith('urls'):
                task_payload['input'][key] = self.upload_files(payload[key])
            elif key not in _exclude_list:
                task_payload['input'][key] = payload[key]
            else:
                self._debug(f"create_task skip key: {key})")
                continue

            # check the key is value NULL or NONE IS NOT VALID
            if task_payload['input'][key] is None:
                self._error(f"create_task empty key {key}: {task_payload['input'][key]}")
                return None

        self._debug(f"create_task payload: {task_payload})")

        if test:
            # send back a fake task_id
            import uuid
            self._task_id = uuid.uuid4().hex  # alphanumeric (32 chars)
            self._warning(f"Callback test mode create a fake task with id: {self._task_id}")
            return self._task_id
        else:
            response = requests.post(KieAIVideoGen._create_task_url, json=task_payload, headers=self._json_header)
            response.raise_for_status()
            if self._check_api_response(response):
                response_json = response.json()
                self._task_id = response_json['data']['taskId']
                return self._task_id
        return None

    @handle_http_exceptions
    def _query_task(self):
        self._debug(f"KieAIVideoGen._query_task()")
        response = requests.get(f"{KieAIVideoGen._query_task_url}?taskId={self._task_id}", headers=self._auth_header)
        response.raise_for_status()
        if self._check_api_response(response):
            return response.json()
        return None

    def _check_task_status(self, query_task_response):
        """
        returns TASK_STATUS for a task query
        """
        self._debug(f"KieAIVideoGen._get_task_status({query_task_response})")
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

    def _log_failure_msg(self, query_task_response):
        self._error(f"Fail code: {query_task_response['data']['failCode']}")
        self._error(f"Fail message: {query_task_response['data']['failMsg']}")

    def _get_result_urls(self, query_task_response):
        self._debug(f"KieAIVideoGen._get_result_urls({query_task_response})")
        return json.loads(query_task_response['data']['resultJson'])['resultUrls']

    def is_finished(self, task_status):
        self._debug(f"KieAIVideoGen._is_finished({task_status})")
        assert(isinstance(task_status, self.TASK_STATUS))
        if task_status in [self.TASK_STATUS.generating, self.TASK_STATUS.waiting, self.TASK_STATUS.queuing]:
            return False
        return True

    def _download_file(self, url, output_path):
        """
        Downloads a file from a URL to a specified path.
        Args:
            url (str): The URL of the file to download.
            output_path (Path): The path to save the downloaded file.
        """
        self._debug(f"KieAIVideoGen._download_file(url={url}, output_path={output_path})")
        try:
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                total_size = int(r.headers.get('content-length', 0))
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
            self._debug(f"Video saved successfully to: {output_path}")
        except requests.exceptions.RequestException as e:
            sys.stdout.write("\n")
            self._error(f"Failed to download video: {e}")

    def _download_videos(self, video_urls):
        self._debug(f"KieAIVideoGen._download_videos(video_urls={video_urls})")
        for video_url in video_urls:
            video_name = video_url.split('/')[-1]
            output_path = Path(self._output_basepath).with_suffix(Path(video_name).suffix)
            self._info(f"Downloading video: {video_url} --> {output_path}")
            self._download_file(video_url, output_path)

    def download_video(self):
        """
        Attempts to download the generated video.
        Returns the TASK_STATUS code of the current task status.
        """
        self._debug(f"KieAIVideoGen.download_video()")

        query_task_response = self._query_task()
        if query_task_response is None:
            return self.TASK_STATUS.unknown
        
        task_status = self._check_task_status(query_task_response)
        if task_status == self.TASK_STATUS.completed:
            self._info("Video generation task complete!")
            self._download_videos(self._get_result_urls(query_task_response))
        elif task_status == self.TASK_STATUS.failed:
            self._error("Attempting to download a failed video generation!!")
            self._log_failure_msg(query_task_response)
        elif task_status == self.TASK_STATUS.unknown:
            self._error(f"Unknown task status!")
        else:
            self._info(f"Task status: {task_status.name}")

        return task_status

class KieAIVideoGen_Veo(KieAIVideoGen):
    """
    """
    def __init__(self, api_key, output_basepath, task_id=None, fullhd=True, path_converter_func=lambda x: x):
        super().__init__(api_key=api_key, output_basepath=output_basepath, task_id=task_id, path_converter_func=path_converter_func)
        self._debug(f"KieAIVideoGen_Veo({api_key}, task_id={task_id}, fullhd={fullhd})")
        self._fullhd = fullhd

    def _check_api_response(self, response):
        # handle veo specific responses
        self._debug(f"KieAIVideoGen_Veo._check_api_response({response})")
        response_json = response.json()
        if response_json['code'] == 400 and self._fullhd: # 1080P is still processing
            self._info("1080P is processing. It should be ready in 1-2 minutes. Please check back shortly.")
            return True
        elif response_json['code'] == 422 and "generate" in response_json['msg'].lower(): # fullhd sometimes returns 422 "Records are being generated"
            self._info(response_json['msg'])
            return True
        # elif response_json['code'] == 500 and self._fullhd: # fullhd mode can return 500 early on in the process
        #     self._info("Records are being generated.")
        #     return True
        return super()._check_api_response(response)

    @handle_http_exceptions
    def create_task(self, payload, test=False):
        self._debug(f"KieAIVideoGen_Veo.generate_video({payload})")
        url = f"{KieAIVideoGen._base_api_url}/veo/generate"

        # make a copy as well need to modify the payload to kie
        gen_payload = payload.copy()

        # check we have an image for i2v
        if gen_payload['generationType'] != "TEXT_2_VIDEO" and  not 'images' in gen_payload:
            self._error(f"No images param in the payload - doesn't seem right!")
            return None

        # upload images and insert resulting imageurl to the payload
        if 'images' in gen_payload and gen_payload['images']:
            gen_payload['imageUrls'] = self.upload_files(gen_payload['images'])
            if not gen_payload['imageUrls'] or None in gen_payload['imageUrls']: return None
            gen_payload.pop('images')

        # start the video generation
        if test:
            # send back a fake task_id
            import uuid
            self._task_id = uuid.uuid4().hex  # alphanumeric (32 chars)
            self._warning(f"Callback test mode create a fake task with id: {self._task_id}")
            return self._task_id
        else:
            response = requests.post(url, json=gen_payload, headers=self._json_header)
            response.raise_for_status()
            if self._check_api_response(response):
                response_json = response.json()
                self._task_id = response_json['data']['taskId']
                self._debug(f"Task ID: {self._task_id}")
                return self._task_id
        return None

    @handle_http_exceptions
    def _query_task(self):
        self._debug(f"KieAIVideoGen_Veo._query_task()")
        if self._fullhd:
            url = f"{KieAIVideoGen._base_api_url}/veo/get-1080p-video?taskId={self._task_id}"  # wait for the 1080P version
        else:
            url = f"{KieAIVideoGen._base_api_url}/veo/record-info?taskId={self._task_id}" # wait for the default version
        response = requests.get(url, headers=self._auth_header)
        response.raise_for_status()
        if self._check_api_response(response):
            return response.json()
        return None

    def _check_task_status(self, query_task_response):
        """
        returns TASK_STATUS for a task query
        """
        self._debug(f"KieAIVideoGen_Veo._get_task_status({query_task_response})")
        if self._fullhd:
            if query_task_response['code'] == 200:
                return self.TASK_STATUS.completed
            else:
                return self.TASK_STATUS.generating
        elif query_task_response['data']['successFlag'] == 0:
            return self.TASK_STATUS.generating
        elif query_task_response['data']['successFlag'] == 1:
            return self.TASK_STATUS.completed
        else:
            return self.TASK_STATUS.failed

    def _log_failure_msg(self, query_task_response):
        self._error(f"Fail code: {query_task_response['data']['errorCode']}")
        self._error(f"Fail message: {query_task_response['data']['errorMessage']}")

    def _get_result_urls(self, query_task_response):
        self._debug(f"KieAIVideoGen_Veo._get_result_urls({query_task_response})")
        if self._fullhd:
            return [query_task_response['data']['result_url']]
        else:
            return query_task_response['data']['response']['resultUrls'] # is it resultUrls or result_urls ?? not HD so we may never know :)





def kie_factory(payload, api_key, output_basepath, task_id=None, path_converter_func=lambda x: x):
    if 'veo' in payload['model'].lower():
        # google veo has it's own api

        # 1080P needs to be explicitly used if required
        fullhd = False
        if 'fullhd' in payload and payload['fullhd']:
            fullhd = True

        # connect to existing task or start a new one
        kie = KieAIVideoGen_Veo(api_key, output_basepath=output_basepath, task_id=task_id, fullhd=fullhd, path_converter_func=path_converter_func)
    else:
        # assume it is the create/query api
        kie = KieAIVideoGen(api_key, output_basepath=output_basepath, task_id=task_id, path_converter_func=path_converter_func)
    return kie

def configure_yaml(path, yaaml):
    # replace tokens with values from the config file located in the same dir
    logging.debug(f"configure_yaml(f{path})")
    config_file_path = os.path.join(path,_CONFIG_FILENAME)
    if config_file_path:
        logging.debug(f"Loading config: {config_file_path}")
        return YamlParamReplacer(config_file_path).replace_tokens(yaaml)
    return yaaml

def yaml_load_payload(yaml_path):
    # read the payload from the yaml
    try:
        with open(yaml_path, 'r') as f:
            payload = configure_yaml(yaml_path.parent, yaml.safe_load(f))
        if not isinstance(payload, dict):
            logging.error(f"SKIPPED: YAML file '{yaml_path.name}' is empty or invalid.")
            return None
    except (yaml.YAMLError, FileNotFoundError) as e:
        logging.error(f"SKIPPED: Could not read or parse YAML file '{yaml_path.name}': {e}")
        return None
    return payload

def yaml_connect_to_existing_tasks(yaml_path, api_key, path_converter_func=lambda x: x):
    logging.info(f"yaml_connect_to_existing_tasks: {yaml_path.name}")

    task_paths = [f for f in yaml_path.parent.glob(f"{Path(yaml_path).stem}*.task")]
    kies = []
    for task_path in task_paths:
        excluded = {'.yaml', '.yml', '.task'}
        file_paths = [f for f in task_path.parent.glob(f"{task_path.stem}.*") if
                      f.suffix.lower() not in excluded]
        logging.debug(f"Found task sidecar possible video files: {file_paths}")
        if not file_paths:
            with open(task_path, 'r') as f:
                task_id = f.readline().strip()
                payload = configure_yaml(task_path.parent, yaml.safe_load(f))
            logging.info(f"Found existing task to attach to {task_id}.")

            kies.append(kie_factory(payload, api_key, task_path.stem, task_id, path_converter_func=path_converter_func))

    return kies

def yaml_create_tasks(yaml_path, api_key, generations=1, test=False, path_converter_func=lambda x: x):
    logging.info(f"yaml_create_tasks: {yaml_path.name}")

    # read the payload from the yaml
    payload = yaml_load_payload(yaml_path)
    if not payload:
        return None
    logging.debug(f"Pre-Payload: f{payload}")

    # check we're not forcing a seed and running multiple generations
    if generations>1 and any('seed' in key.lower() for key in payload):
        logging.error(f"SKIPPED: Requested multiple generates with a seed value, doesn't seem right! '{yaml_path.name}'")
        return None

    # find existing generations
    task_gens_dict = {}
    for f in yaml_path.parent.glob(f"{yaml_path.stem}*.task"):
        if f.is_file() and (m := re.search(r'_(\d{5})$', f.stem)):
            logging.debug(f"Found existing generation file '{f}'")
            task_gens_dict[int(m.group(1))] = f

    # what is the next generation
    start_generation = 0
    if task_gens_dict:
        start_generation = max(task_gens_dict.keys())+1
    logging.info(f"Generation start index: {start_generation}.")

    # create a task for each generation
    kies = []
    for generation in range(start_generation, start_generation+generations):
        logging.info(f"Generation: {generation}")

        task_id_path = yaml_path.with_stem(f"{yaml_path.stem}_{generation:05d}").with_suffix(".task")
        output_basepath = task_id_path.stem # remove the extension

        # model specific factory creation
        kie = kie_factory(payload, api_key, output_basepath, path_converter_func=path_converter_func)

        # start the video gen
        task_id = kie.create_task(payload, test=test)
        if not task_id: continue
        with open(task_id_path, 'w') as f:
            f.write(f"{task_id}\n")
            yaml.dump(payload, f)

        kies.append(kie)

    return kies
        
def main(path_converter_func=lambda x: x):
    global _TASKS_WAITING_QUEUE
    
    parser = argparse.ArgumentParser(
        description="Generate videos from YAML files using the kie.ai API.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Local image files are uploaded with parameter handling as follows:
  - image becomes image_url
  - images becomes image_urls
  - inputs becomes input_urls
 
Example Usage:
  - Process a single file:
    ./genlab.py my_video.yaml

  - Process multiple files:
    ./genlab.py project/vid1.yaml project/vid2.yaml

  - Process all .yaml/.yml files in a directory:
    ./genlab.py /path/to/yamls/
"""
    )
    parser.add_argument(
        "paths",
        metavar="PATH",
        nargs="+",
        help="One or more paths to .yaml files or directories containing them."
    )
    parser.add_argument(
        "-g", "--generations",
        type=int, default=1,
        help="Number of video versions to generate per yaml (also known as number of seeds)."
    )
    parser.add_argument(
        "-d", "--download",
        action="store_true",
        help="Download the video files of existing tasks (do not create any new tasks, --generations is ignored)."
    )
    parser.add_argument(
        "--retry_wait_secs",
        type=int, default=20,
        help="Number of seconds to wait before retrying, AKA polling wait time."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug level logging to show detailed request information."
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test, do everything but actually submit a generation task."
    )
    args = parser.parse_args()

    # --- Handler 1: INFO and above to terminal (stdout) ---
    console_handler = logging.StreamHandler(sys.stdout)
    if args.debug:
        console_handler.setLevel(logging.DEBUG)
    else:
        console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('[%(levelname)s] %(message)s')
    console_handler.setFormatter(console_format)

    # --- Handler 2: DEBUG and above to file ---
    file_handler = logging.FileHandler('genlab.log')
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    file_handler.setFormatter(file_format)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    logging.info(f"----------------------------------------------------------------------------------------")
    logging.info(f"-----------------------------------GENLAB-----------------------------------------------")
    logging.info(f"----------------------------------------------------------------------------------------")
    logging.info(f"genlab is running: {vars(args)}")

    global _API_KEY
    try:
        _API_KEY = os.environ["KIE_API_KEY"]
    except KeyError:
        logging.critical("FATAL: KIE_API_KEY environment variable not set.")
        logging.critical("Please set your API key, e.g., 'export KIE_API_KEY=\"your_key\"'")
        sys.exit(-50)

    if args.download:
        logging.warning("Download mode - will only download videos of existing tasks, no new tasks will be created.")

    yaml_files = []
    for path_str in args.paths:
        for path in [Path(p) for p in glob.glob(path_str)]:
            if path.is_dir():
                yaml_files.extend(sorted(path.glob("*.yaml")))
                yaml_files.extend(sorted(path.glob("*.yml")))
            elif path.is_file() and path.suffix.lower() in [".yaml", ".yml"]:
                yaml_files.append(path)
            else:
                logging.warning(f"Path '{path_str}' is not a valid file or directory. Ignoring.")

    # filter out known yamls
    check_yaml_files = yaml_files
    yaml_files = []
    for yaml_file in check_yaml_files:
        if yaml_file.name not in [_CONFIG_FILENAME]:
            yaml_files.append(yaml_file)

    if not yaml_files:
        logging.error("No .yaml or .yml files found in the specified paths.")
        sys.exit(1)

    logging.info(f"Found {len(yaml_files)} YAML file(s) to process.")
    for yaml_path in yaml_files:
        if args.download:
            kies = yaml_connect_to_existing_tasks(yaml_path, _API_KEY, path_converter_func=path_converter_func)
        else:
            kies = yaml_create_tasks(yaml_path, _API_KEY, generations=args.generations, test=args.test, path_converter_func=path_converter_func)
            if len(kies) != args.generations:
                logging.warning(f"{yaml_path.name} some generations did not start.")
        if kies:
            _TASKS_WAITING_QUEUE.extend(kies)
        elif not args.download:
            logging.warning(f"{yaml_path} failed or nothing to do!")

    if not _TASKS_WAITING_QUEUE:
        logging.error(f"Nothing to do!")
        exit(-67)
        
    logging.info("Waiting for all tasks to be completed.")
    retry = 0
    while retry < 9999:
        logging.info(f"Tasks waiting in the queue: {_TASKS_WAITING_QUEUE}")
        
        # check each task
        completed_tasks = []
        for kie in _TASKS_WAITING_QUEUE:

            # try downloading the video
            status = kie.download_video()

            # is this task finished?
            if kie.is_finished(status):
                # remove from the list
                completed_tasks.append(kie)

        # remove completed from the queue (outside loop to avoid corrupting the very list it is checking)
        #for id in completed_tasks: _TASKS_WAITING_QUEUE.pop(id, None)
        _TASKS_WAITING_QUEUE = [kie for kie in _TASKS_WAITING_QUEUE if kie not in completed_tasks]

        # check if there are any left
        if not _TASKS_WAITING_QUEUE:
            break

        retry += 1
        logging.info(f"Waiting {args.retry_wait_secs}s for all jobs to be completed, retry {retry}.")
        time.sleep(args.retry_wait_secs)

    logging.info(f"All tasks completed!")
    


if __name__ == "__main__":
    _DEFAULT_MAPPINGS = [ # should load this from a config file
            {"win": r"X:", "osx": "/Volumes/projects"}
        ]
    path_converter = NetworkPathConverter(_DEFAULT_MAPPINGS)

    main(path_converter_func=path_converter.convert)
