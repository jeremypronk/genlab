import requests
import yaml
import json
import datetime
import os
import time
import logging
import sys
import functools
import argparse
import re
from pathlib import Path
from enum import Enum

_API_KEY = None
_TASKS_WAITING_QUEUE = []

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

class KieAIVideoGen:
    """
    """
    _api_server = "https://api.kie.ai"
    _base_api_url = f"{_api_server}/api/v1"
    _create_task_url = f"{_base_api_url}/jobs/createTask"
    _query_task_url = f"{_base_api_url}/jobs/recordInfo"
    _upload_url = f"https://kieai.redpandaai.co/api/file-stream-upload"
    _file_url = None

    class TASK_STATUS(Enum):
        completed = 1
        failed = 2
        generating = 3
        waiting = 4
        queuing = 5
        unknown = 6

    def __init__(self, api_key, output_path, task_id=None):
        logging.debug(f"KieAIVideoGen({api_key}, {task_id})")
        self._api_key = api_key
        self._output_path = Path(output_path)
        self._task_id = task_id
        self._auth_header = {
            "Authorization": f"Bearer {self._api_key}",
        }
        self._json_header = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }

    def __repr__(self):
        return f"KieAIVideoGen({self._task_id}, {self._output_path})"

    def _name(self):
        return self._output_path.stem

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
        self._debug(f"KieAIVideoGen.upload_file({file_path})")
        if not os.path.exists(file_path):
            self._error(f"File not found at path: {file_path}")
            return None

        files = {
            'file': (os.path.basename(file_path), open(file_path, 'rb')),
            'uploadPath': (None, 'images/user-uploads'),
            'fileName': (None, os.path.basename(file_path))
        }
        self._debug(f"Preparing to upload '{files}'...")
        response = requests.post(self._upload_url, headers=self._auth_header, files=files)
        response.raise_for_status()
        if self._check_api_response(response):
            response_data = response.json()["data"]

            # Extract the URL from the JSON response.
            self._file_url = response_data.get("downloadUrl")
            if self._file_url:
                self._info(f"File URL: {self._file_url}")
                return self._file_url
            else:
                self._error("URL not found in API response.")
        return None

    def upload_images(self, images):
        self._debug(f"KieAIVideoGen.upload_images({images})")
        # upload images and return urls to uploaded images
        image_urls = list()
        if not isinstance(images, list):
            images = [images]
        for image in images:
            image_urls.append(self.upload_file(image))
        return image_urls

    @handle_http_exceptions
    def create_task(self, payload, test=False):
        """
        image becomes image_url
        images becomes image_urls
        """
        self._debug(f"KieAIVideoGen.create_task({payload})")

        input_payload = {}
        for key in payload.keys():
            if key not in ['model', 'image', 'images']:
                input_payload[key] = payload[key]

        if 'image' in input_payload and 'images' in input_payload:
            self._error("image and images keys found!")
            return None

        if 'image' in payload:
            upload_file = self.upload_file(payload['image'])
            if upload_file:
                input_payload['image_url'] = upload_file
            else:
                return None
        elif 'images' in payload:
            input_payload['image_urls'] = self.upload_images(payload['images'])
            if not input_payload['image_urls'] or None in input_payload['image_urls']: return None

        task_payload = dict()
        task_payload['model'] = payload['model']
        task_payload['input'] = input_payload

        self._info(f"create_task payload: {task_payload})")

        if test:
            # send back a fake task_id
            import uuid
            self._task_id = uuid.uuid4().hex  # alphanumeric (32 chars)
            self._warning(f"Callback test mode create a fake task with id: {self._task_id}")
            return self._task_id
        else:
            response = requests.post(self._create_task_url, json=task_payload, headers=self._json_header)
            response.raise_for_status()
            if self._check_api_response(response):
                response_json = response.json()
                self._task_id = response_json['data']['taskId']
                return self._task_id
        return None

    @handle_http_exceptions
    def _query_task(self):
        self._debug(f"KieAIVideoGen._query_task()")
        response = requests.get(f"{self._query_task_url}?taskId={self._task_id}", headers=self._auth_header)
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

    def _download_video(self, url, output_path):
        """
        Downloads a file from a URL to a specified path.
        Args:
            url (str): The URL of the file to download.
            output_path (Path): The path to save the downloaded file.
        """
        self._debug(f"KieAIVideoGen._download_video(url={url}, output_path={output_path})")
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

    def _download_videos(self, video_urls, output_path):
        self._debug(f"KieAIVideoGen._download_videos(video_urls={video_urls}, output_path={output_path})")
        for video_url in video_urls:
            video_name = video_url.split('/')[-1]
            output_path = Path(output_path).with_suffix(Path(video_name).suffix)
            self._info(f"Downloading video: {video_url} --> {output_path}")
            self._download_video(video_url, output_path)

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
            self._download_videos(self._get_result_urls(query_task_response), self._output_path)
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
    def __init__(self, api_key, output_path, task_id=None, fullhd=True):
        super().__init__(api_key=api_key, output_path=output_path, task_id=task_id)
        self._debug(f"KieAIVideoGen_Veo({api_key}, task_id={task_id}, fullhd={fullhd})")
        self._fullhd = fullhd

    def _check_api_response(self, response):
        # handle veo specific responses
        self._debug(f"KieAIVideoGen_Veo._check_api_response({response})")
        response_json = response.json()
        if response_json['code'] == 400 and self._fullhd: # 1080P is still processing
            self._info("1080P is processing. It should be ready in 1-2 minutes. Please check back shortly.")
            return True
        elif response_json['code'] == 422 and self._fullhd: # fullhd returns 422 "Records are being generated"
            self._info("Records are being generated.")
            return True
        # elif response_json['code'] == 500 and self._fullhd: # fullhd mode can return 500 early on in the process
        #     self._info("Records are being generated.")
        #     return True
        return super()._check_api_response(response)

    @handle_http_exceptions
    def create_task(self, payload, test=False):
        self._debug(f"KieAIVideoGen_Veo.generate_video({payload})")
        url = f"{self._base_api_url}/veo/generate"

        # make a copy as well need to modify the payload to kie
        gen_payload = payload.copy()

        # upload images and insert resulting imageurl to the payload
        if 'images' in gen_payload and gen_payload['images']:
            gen_payload['imageUrls'] = self.upload_images(gen_payload['images'])
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
            url = f"{self._base_api_url}/veo/get-1080p-video?taskId={self._task_id}"  # wait for the 1080P version
        else:
            url = f"{self._base_api_url}/veo/record-info?taskId={self._task_id}" # wait for the default version
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




def backup_sidecar_files(file_paths):
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for file_path in file_paths:
        file_path_backup = f"{file_path.stem}_bk{timestamp}{file_path.suffix}"
        logging.warning(f"RENAMING: Backing up sidecar file '{file_path}' to {file_path_backup}")
        file_path.rename(file_path_backup)

def process_yaml(yaml_path, api_key, generations=1, download=False, test=False):
    logging.info(f"Processing: {yaml_path.name}")

    if download:
        logging.error(f"SKIPPING {yaml_path} download not yet implemented!")
        return None

    # find existing generations
    task_gens_dict = {}
    for f in Path(yaml_path).parent.glob(f"{Path(yaml_path).stem}*.task"):
        if f.is_file() and (m := re.search(r'_(\d{5})$', f.stem)):
            task_gens_dict[int(m.group(1))] = f

    start_generation = 0
    if task_gens_dict:
        start_generation = max(task_gens_dict.keys())+1

    logging.info(f"Generation start index: {start_generation}.")


    return

    # we will backup the sidecar files if forcing
    sidecar_files_to_backup =  []

    # check we havent already gen'd this video
    excluded = {'.yaml', '.yml', '.task'}
    file_paths = [f for f in Path(yaml_path).parent.glob(f"{Path(yaml_path).stem}.*") if f.suffix.lower() not in excluded]
    logging.debug(f"Found yaml sidecar possible video files: {file_paths}")
    if len(file_paths) > 0:
        if force:
            sidecar_files_to_backup += file_paths
        else:
            logging.warning(f"SKIPPING: Output files '{file_paths}' already exist!")
            return

    # check if a task id exists, then we will connect to the running task
    task_id = None
    task_id_path = yaml_path.with_suffix(".task")
    if task_id_path.exists():
        if force:
            logging.warning(f"Ignoring existing task file {task_id_path}.")
            sidecar_files_to_backup.append(task_id_path)
        else:
            with open(task_id_path, 'r') as f:
                task_id = f.read()
            logging.info(f"Found existing task to attach to {task_id}.")

    # backup sidecar files
    if sidecar_files_to_backup:
        backup_sidecar_files(sidecar_files_to_backup)

    # read the payload from the yaml
    try:
        with open(yaml_path, 'r') as f:
            payload = yaml.safe_load(f)
        if not isinstance(payload, dict):
            logging.error(f"SKIPPED: YAML file '{yaml_path.name}' is empty or invalid.")
            return
    except (yaml.YAMLError, FileNotFoundError) as e:
        logging.error(f"SKIPPED: Could not read or parse YAML file '{yaml_path.name}': {e}")
        return

    logging.info(f"Pre-Payload: f{payload}")

    # model specific factory creation
    if 'veo' in payload['model'].lower():
        # google veo has it's own api

        # 1080P needs to be explicitly used if required
        fullhd = False
        if 'fullhd' in payload and payload['fullhd']:
            fullhd = True

        # connect to existing task or start a new one
        kie = KieAIVideoGen_Veo(api_key, output_path=yaml_path, task_id=task_id, fullhd=fullhd)
    else:
        # assume it is the create/query api
        kie = KieAIVideoGen(api_key, output_path=yaml_path, task_id=task_id)

    # start the video gen
    if not task_id:  # only if we dont have an existing task
        task_id = kie.create_task(payload, test=test)
        if not task_id: return None
        with open(task_id_path, 'w') as f:
            f.write(task_id)

    return kie
        
def main():
    global _TASKS_WAITING_QUEUE
    
    parser = argparse.ArgumentParser(
        description="Generate videos from YAML files using the kie.ai API.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
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
        help="Download the video files of existing tasks (do not create any new tasks, --seeds is ignored)."
    )
    parser.add_argument(
        "-r", "--retry_wait_secs",
        type=int, default=20,
        help="Number of seconds to wait before retrying, AKA polling wait time."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug level logging to show detailed request information."
    )
    parser.add_argument(
        "-t", "--test",
        action="store_true",
        help="Test, do everything but actually submit a generation task."
    )
    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

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
        path = Path(path_str)
        if path.is_dir():
            yaml_files.extend(sorted(path.glob("*.yaml")))
            yaml_files.extend(sorted(path.glob("*.yml")))
        elif path.is_file() and path.suffix.lower() in [".yaml", ".yml"]:
            yaml_files.append(path)
        else:
            logging.warning(f"Path '{path_str}' is not a valid file or directory. Ignoring.")

    if not yaml_files:
        logging.error("No .yaml or .yml files found in the specified paths.")
        sys.exit(1)

    logging.info(f"Found {len(yaml_files)} YAML file(s) to process.")
    for yaml_path in yaml_files:
        kie = process_yaml(yaml_path, _API_KEY, generations=args.generations, download=args.download, test=args.test)
        if kie:
            _TASKS_WAITING_QUEUE.append(kie)
        else:
            logging.error(f"{yaml_path.name} failed, skipping.")
        
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
    main()
