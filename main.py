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
from pathlib import Path
from enum import Enum



_API_KEY = None
_TASKS_WAITING_QUEUE = dict()


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

    def _api_response(self, response):
        response_json = response.json()
        self._debug(f"KieAIVideoGen._api_response({response_json})")
        if response_json['code'] == 200:
            self._debug(f"Request was successful.")
            return response_json
        elif response_json['code'] == 400:
            self._error(f"Content violation error, check your prompt and/or input images for content that violates the T&Cs.")
            exit(-98)
        elif response_json['code'] == 401:
            self._error(f"NO ACCESS PERMISSION!! Check your api key.")
            exit(-99)
        else:
            self._error(f"Unknown error ({response_json})")
            exit(-97)
        return response_json

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
        response_data = self._api_response(response)["data"]

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
        imageUrls = []
        for image in images:
            imageUrls.append(self.upload_file(image))
        return imageUrls

    @handle_http_exceptions
    def create_task(self, payload):
        self._debug(f"KieAIVideoGen.create_task({payload})")

        input_payload = {}
        for key in payload.keys():
            if key not in ['model', 'image', 'images']:
                input_payload[key] = payload[key]

        if 'image' in payload:
            input_payload['image_url'] = self.upload_file(payload['image'])
        elif 'images' in payload:
            self._error("NOT SUPPORTED")
            exit(-200)

        task_payload = {}
        task_payload['model'] = payload['model']
        task_payload['input'] = input_payload

        logging.info(f"create_task payload: {task_payload})")

        response = requests.post(self._create_task_url, json=task_payload, headers=self._json_header)
        response.raise_for_status()
        response_json = self._api_response(response)
        self._task_id = response_json['data']['taskId']
        return self._task_id

    @handle_http_exceptions
    def _query_task(self):
        self._debug(f"KieAIVideoGen._query_task()")
        response = requests.get(f"{self._query_task_url}?taskId={self._task_id}", headers=self._auth_header)
        response.raise_for_status()
        #response_json_data = self._api_response(response)['data']
        return response

    def _check_task_status(self, query_task_response):
        """
        returns task_status
        """
        self._debug(f"KieAIVideoGen._get_task_status()")
        state = query_task_response['state']
        # _task_state_success = "success"
        # _task_state_fail = "fail"
        if "success" in state.lower():
            return TASK_STATUS.completed
        elif "fail" in state.lower():
            return TASK_STATUS.failed
        elif "gen" in state.lower():
            return TASK_STATUS.generating
        elif "wait" in state.lower():
            return TASK_STATUS.waiing
        elif "que" in state.lower():
            return TASK_STATUS.queuing
        else:
            return TASK_STATUS.unknown

    # def wait_for_completion(self, retries=10, retry_wait_secs=30):
    #     logging.debug(f"KieAIVideoGen.wait_for_completion(retries={retries}, retry_wait_secs={retry_wait_secs})")
    #     retry = 0
    #     while retry < retries:
    #         result = self._check_status()
    #         if result is not None:
    #             return result
    #         time.sleep(retry_wait_secs)
    #         retry += 1
    #     return retry < retries

    def _download_video(self, url, output_path):
        """
        Downloads a file from a URL to a specified path.
        Args:
            url (str): The URL of the file to download.
            output_path (Path): The path to save the downloaded file.
        """
        self._debug(f"KieAIVideoGen._download_video({url}, {output_path})")
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
        logging.debug(f"KieAIVideoGen._download_videos(video_urls={video_urls}, output_path={output_path})")
        for video_url in video_urls:
            video_name = video_url.split('/')[-1]
            output_path = Path(output_path).with_suffix(Path(video_name).suffix)
            logging.info(f"Downloading video: {video_url} --> {output_path}")
            self._download_video(video_url, output_path)

    def _log_failure_msg(self):
        self._error(f"Fail code: {query_data['failCode']}")
        self._error(f"Fail message: {query_data['failMsg']}")

    def download_video(self):
        logging.debug(f"KieAIVideoGen.download_video()")

        query_task_response = self._query_task()
        task_status = self._check_task_status(query_task_response_)
        if task_status == TASK_STATUS.completed:
            self._info("Video generation task complete!")
            self._download_videos(json.loads(query_task_response['data']['resultJson'])['resultUrls'], self._output_path)
        elif task_status == TASK_STATUS.failed:
            self._error("Attempting to download a failed video generation!!")
            self._log_failure_msg()
        elif task_status == TASK_STATUS.unknown:
            self._error(f"({self._name()} Unknown task status!")
        else:
            self._info(f"({self._name()} Task status: {task_status.name}")

        return task_status


class KieAIVideoGen_Veo(KieAIVideoGen):
    """
    """
    def __init__(self, api_key, task_id=None, fullhd=True):
        logging.debug(f"KieAIVideoGen_Veo({api_key}, task_id={task_id}, fullhd={fullhd})")
        super().__init__(api_key=api_key, task_id=task_id)
        self._fullhd = fullhd

    def _api_response(self, response):
        # handle veo specific responses
        response_json = response.json()
        logging.debug(f"KieAIVideoGen_Veo._api_response({response_json})")
        if response_json['code'] == 400 and self._fullhd: # fullhd returns 400 when it is still processing
            return response_json
        if response_json['code'] == 422 and self._fullhd: # fullhd returns 422 "Records are being generated"
            return response_json
        elif response_json['code'] == 500 and self._fullhd: # fullhd mode can return 500 early on in the process
            return response_json
        else:
            response_json = super()._api_response(response)
        return response_json

    @handle_http_exceptions
    def generate_video(self, payload):
        logging.debug(f"KieAIVideoGen_Veo.generate_video({payload})")
        url = f"{self._base_api_url}/veo/generate"

        # upload images and insert resulting imageurl to the payload
        if 'images' in payload and payload['images']:
            images = payload['images']
            if isinstance(images, str):
                images = [images]
            payload['imageUrls'] = self.upload_images(images)

        # generate the video
        response = requests.post(url, json=payload, headers=self._json_header)
        response.raise_for_status()
        response_json = self._api_response(response)

        self._task_id = response_json['data']['taskId']
        logging.info(f"Task ID: {self._task_id}")

        return self._task_id

    @handle_http_exceptions
    def _check_status(self, ):
        """
        returns True if completed (could be failed) False if other (in queue, generating, waiting)
        """
        if self._fullhd:
            url = f"{self._base_api_url}/veo/get-1080p-video?taskId={self._task_id}"  # wait for the 1080P version
        else:
            url = f"{self._base_api_url}/veo/record-info?taskId={self._task_id}" # wait for the default version
        response = requests.get(url, headers=self._auth_header)
        response.raise_for_status()
        response_json = self._api_response(response)

        if self._fullhd:
            status = 1 if response_json['code'] == 200 else 0
        else:
            status = response_json['data']['successFlag']
        if status == 0:
            logging.info("Still generating...")
            return None
        elif status == 1:
            logging.info("Generation successful!")
            return True
        else:
            logging.info(f"Generation failed: {response_json['msg']}")
            return False

    @handle_http_exceptions
    def download_video(self):
        logging.debug(f"KieAIVideoGen_Veo.download_video()")
        if self._fullhd:
            url = f"{self._base_api_url}/veo/get-1080p-video?taskId={self._task_id}"  # 1080P version
        else:
            url = f"{self._base_api_url}/veo/record-info?taskId={self._task_id}" # default version
        response = requests.get(url, headers=self._auth_header)
        response.raise_for_status()
        response_json = self._api_response(response)
        if self._fullhd:
            video_urls = [response_json['data']['resultUrl']]
        else:
            video_urls = response_json['data']['response']['resultUrls']

        self._download_videos(video_urls, self._output_path)






def backup_sidecar_files(file_paths):
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for file_path in file_paths:
        file_path_backup = f"{file_path.stem}_bk{timestamp}{file_path.suffix}"
        logging.warning(f"RENAMING: Backing up sidecar file '{file_path}' to {file_path_backup}")
        file_path.rename(file_path_backup)

def process_yaml(yaml_path, api_key, force=False):
    logging.info(f"Processing: {yaml_path.name}")

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

        # # start the video gen
        # if not task_id:  # only if we dont have an existing task
        #     task_id = kie.generate_video(payload)
        #     with open(task_id_path, 'w') as f:
        #         f.write(task_id)

        # # wait for task to complete
        # if not kie.wait_for_completion(retries=10):
        #     logging.error(f"Timed out waiting for completion of {kie._task_id}.")
        #     return -1

        # # download the video
        # kie.download_video(yaml_path)
    else:
        # assume it is the create/query api
        kie = KieAIVideoGen(api_key, output_path=yaml_path, task_id=task_id)

    # start the video gen
    if not task_id:  # only if we dont have an existing task
        task_id = kie.create_task(payload)
        with open(task_id_path, 'w') as f:
            f.write(task_id)
    # else:
    #     connected_to_existing_task = True

    # # wait for task to complete if not using the callback
    # if not use_callback or connected_to_existing_task:
    #     if not kie.wait_for_completion(retries=10):
    #         logging.error(f"Timed out waiting for completion of {kie._task_id}.")
    #         return -1

    #     # download the video
    #     kie.download_video(yaml_path)

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
        "-d", "--debug",
        action="store_true",
        help="Enable debug level logging to show detailed request information."
    )
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Force generation of videos even if they already exist locally."
    )
    # parser.add_argument(
    #     "-c", "--use_callback",
    #     action="store_true",
    #     help="For create task jobs (not Google Veo), use the callback process instead of one-by-one generations."
    # )
    # parser.add_argument(
    #     "-t", "--test_callback",
    #     action="store_true",
    #     help="When using the callback process, test mode will create a fake task rather than sending the task to Kie - useful for testing."
    # )
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

    if args.force:
        logging.warning("Forcing generation of videos even if they already exist locally.")

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

    # _cb_server = None
    # if args.use_callback:
    #     logging.info("Starting the callback server.")
    #     if not _cb_server:
    #         _cb_server = callback_server.CallbackServer(local_port=5001, external_port=6666, callback=download_video_callback)
    #         _cb_server.start()  # non-blocking
    #         logging.info(f"Public callback URL: {_cb_server.get_callback_url("callback")}")
    #         logging.info(f"Local callback URL: {_cb_server.get_local_callback_url("callback")}")

    logging.info(f"Found {len(yaml_files)} YAML file(s) to process.")
    for yaml_path in yaml_files:
        kie = process_yaml(yaml_path, _API_KEY, force=args.force)
        _TASKS_WAITING_QUEUE[kie._task_id] = kie
        

    # if args.use_callback:
    #     logging.info("Waiting for all callback jobs to be completed.")
    #     retry_wait_secs = 30

    #     retry = 0
    #     while retry < 9999:
    #         logging.debug(f"Tasks waiting queue: {_TASKS_WAITING_QUEUE}")
    #         if not _TASKS_WAITING_QUEUE:
    #             logging.info(f"All tasks completed!")
    #             break
    #         time.sleep(retry_wait_secs)
    #         retry += 1
    #         logging.info(f"Waiting for all callback jobs to be completed, retry {retry}.")

    #     logging.info(f"All tasks completed! Stopping the callback server.")
    #     _cb_server.stop()

    logging.info("Waiting for all jobs to be completed.")

    retry_wait_secs = 30
    while retry < 9999:
        logging.info(f"Tasks waiting in the queue: {_TASKS_WAITING_QUEUE}")
        
        # check each task
        completed_tasks = []
        for kie in _TASKS_WAITING_QUEUE.itervalues():

            # try downloading the video
            status = kie.download_video(output_path)

            # still gening?
            if status in [kie.TASK_STATUS.generating, kie.TASK_STATUS.waiting, kie.queuing]
                continue

            # otherwise remove from the list
            completed_tasks.append(kie._task_id)

        # remove completed from the queue      
        for id in completed_tasks: _TASKS_WAITING_QUEUE.pop(id, None)

        # check if there are any left
        if not _TASKS_WAITING_QUEUE:
            logging.info(f"All tasks completed!")
            break
        
        time.sleep(retry_wait_secs)
        retry += 1
        logging.info(f"Waiting for all jobs to be completed, retry {retry}.")

    logging.info(f"All tasks completed!")
    


if __name__ == "__main__":
    main()



"""

Invoke-RestMethod -Uri "http://202.171.178.2:6666/callback" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{
    "code": 200,
    "data": {
        "completeTime": 1755599644000,
        "consumeCredits": 100,
        "costTime": 8,
        "createTime": 1755599634000,
        "model": "bytedance/v1-pro-image-to-video",
        "param": "{\"callBackUrl\":\"https://your-domain.com/api/callback\",\"model\":\"bytedance/v1-pro-image-to-video\",\"input\":{\"prompt\":\"A golden retriever dashing through shallow surf at the beach, back angle camera low near waterline, splashes frozen in time, blur trails in waves and paws, afternoon sun glinting off wet fur, overcast day, dramatic clouds\",\"image_url\":\"https://file.aiquickdraw.com/custom-page/akr/section-images/1755179021328w1nhip18.webp\",\"resolution\":\"720p\",\"duration\":\"5\",\"camera_fixed\":false,\"seed\":-1,\"enable_safety_checker\":true}}",
        "remainedCredits": 2510330,
        "resultJson": "{\"resultUrls\":[\"["https://tempfile.aiquickdraw.com/f/c6a8410f94f6916ab3bab0169178d72c_1757911713_zyervt7q.mp4"]\"]}",
        "state": "success",
        "taskId": "c6a8410f94f6916ab3bab0169178d72c",
        "updateTime": 1755599644000
    },
    "msg": "Playground task completed successfully."
}'



"""
