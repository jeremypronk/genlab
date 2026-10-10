import os
import requests
import json
from pathlib import Path
import av

from . import GenAPI
from . import handle_http_exceptions, get_safe_filename


def get_video_source(file_path):
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    file_size = os.path.getsize(file_path)
    _, extension = os.path.splitext(file_path)
    container_ext = extension.lower().lstrip('.')

    # Open video container with PyAV
    with av.open(file_path) as container:
        # Fetch the primary video stream
        video_stream = container.streams.video[0]
        
        # Frame rate is stored as a Fraction (e.g., 30/1 or 30000/1001)
        fps = float(video_stream.average_rate or video_stream.rate or 0)
        
        # Container duration is measured in microseconds (av.TIME_BASE = 1,000,000)
        if container.duration is not None:
            duration = container.duration / av.time_base
        elif video_stream.duration and video_stream.time_base:
            duration = float(video_stream.duration * video_stream.time_base)
        else:
            duration = 0.0

        # Frame count from header, with fallback estimate if missing
        frame_count = video_stream.frames
        if not frame_count and fps > 0 and duration > 0:
            frame_count = int(duration * fps)

        return {
            "container": container_ext,
            "size": file_size,
            "duration": round(duration, 2),
            "frameCount": frame_count,
            "frameRate": round(fps, 2),
            "resolution": {
                "width": video_stream.width,
                "height": video_stream.height
            }
        }

    # return {
    #     "container": "mp4",
    #     "size": 1000,
    #     "duration": 2.4,
    #     "frameCount": 100,
    #     "frameRate": 24.0,
    #     "resolution": {
    #         "width": 1280,
    #         "height": 720
    #     }
    # }

class TopazGen(GenAPI):
    """
    Concrete implementation of the Topaz API
    https://developer.topazlabs.com/

    You can pass your api key in the environment variable TOPAZ_API_KEY or to the class constructor
    """
    API_SERVER = "https://api.topazlabs.com/video/"
    ACCEPT_URL = API_SERVER+"{REQUEST_ID}/accept"
    COMPLETE_URL = API_SERVER+"{REQUEST_ID}/complete-upload/"
    STATUS_URL = API_SERVER+"{REQUEST_ID}/status"
    API_KEY = None

    PLATFORM = "topaz"

    ENABLE_UPLOAD_CACHE = False # doesnt work for topaz

    def __init__(self, output_basepath, api_key=None, path_converter_func=lambda x: x):
        super().__init__(output_basepath, path_converter_func=path_converter_func)
        # TODO: api key stuff could move to the base class
        if not api_key:
            try:
                TopazGen.API_KEY = os.environ["TOPAZ_API_KEY"]
            except KeyError:
                self._error("FATAL: TOPAZ_API_KEY environment variable is not set.")
                self._error("Please set your API key, e.g., 'export TOPAZ_API_KEY=\"your_key\"'")
            self._info("Topaz api key found in environment variable TOPAZ_API_KEY")
        else:
            self._info("Topaz api key passed in constructor")
            TopazGen.API_KEY = api_key

        self.HEADER = {"X-API-Key": TopazGen.API_KEY}
        self.JSON_HEADER |= self.HEADER
        self.ACCEPT_HEADER = self.HEADER | {"Accept":"*/*"}

    def _download(self, query_task_response):
        """
        For details on the contents of the task response see,
        https://developer.topazlabs.com/reference/video/get-request-status/get-video-request-status
        Args:
            query_task_response: topaz task response
        """
        self._debug(f"TopazGen._download(query_task_response={query_task_response})")

        url = query_task_response['download']['url']
        name = get_safe_filename(url)
        output_path = Path(self._output_basepath).with_suffix(Path(name).suffix)

        self._info(f"Downloading file: {url} --> {output_path}")
        self.download_file(url, output_path)

    # def prep_param(self, param, value) -> tuple:
    #     """
    #     kie.ai legacy image payload params are named image_input and video payload image and video reference params
    #     all end in _url (single ref) or _urls (list of refs).
    #     Uploads url params if they contain a path to a local file, replacing path value with the new url.
    #     (upload_file() handles input urls by simple returning the input path)
    #     Args:
    #         param task/request parameter
    #         value task/request value

    #     Returns:
    #         tuple of task ready param,value pair.
    #     """
    #     if param.endswith('url'):
    #         value = self.upload_file(value) # returns a string
    #     elif param.strip().lower() == 'image_input' or param.endswith('urls'):
    #         value = self.upload_files(value) # returns a list of strings
    #         if None in value: value = None # fail on any missing input path

    #     return (param, value)

    def _check_api_response(self, response) -> bool:
        """
        Basic api response check. Override this method in subclasses for more granular checking.
        Args:
            response: the response from the API (json string)

        Returns:
            bool True if response code is 200, False otherwise.
        """
        self._debug(f"TopazGen._check_api_response({response})")
        if response.status_code == 200 or response.status_code == 202:
            self._debug("Request was successful.")
            return True

        response_json = response.json()
        if 'message' in response_json:
            self._error(f"Error: API response code:- {response.status_code} API response msg:- {response_json['message']}")
        else:
            self._error(f"Unknown error ({response_json})")
        return False

    def _get_task_status(self, query_task_response):
        """
        returns TASK_STATUS for a task query
        """
        self._debug(f"TopazGen._get_task_status({query_task_response})")
        task_response_status = query_task_response['status']
        if "complete" in task_response_status.lower():
            return self.TASK_STATUS.completed
        elif "fail" in task_response_status.lower():
            return self.TASK_STATUS.failed
        elif "initializing" in task_response_status.lower() or "processing" in task_response_status.lower():
            return self.TASK_STATUS.generating
        # elif "wait" in task_response_status.lower():
        #     return self.TASK_STATUS.waiting
        elif "requested" in task_response_status.lower() or "accepted" in task_response_status.lower():
            return self.TASK_STATUS.queuing
        else:
            return self.TASK_STATUS.unknown

    @handle_http_exceptions
    def query_task(self) -> tuple:
        """
        For details on the contents of the task response see,
        https://developer.topazlabs.com/reference/video/get-request-status/get-video-request-status
        """
        self._debug(f"TopazGen.query_task()")
        response = requests.get(TopazGen.STATUS_URL.format(REQUEST_ID=self._task_id), headers=self.HEADER)
        response.raise_for_status()
        if self._check_api_response(response):
            response_json = response.json()
            return (self._get_task_status(response_json), response_json)
        return (None, None)

    def _upload_file(self, path: str | Path):

        if self._upload_urls:

            with open(path, "rb") as f:
                put = requests.put(self._upload_urls[0], data=f.read())

            put.raise_for_status()

            # print(put.headers)
            if "ETag" in put.headers:
                self._etag = put.headers["ETag"].strip('"')
                return self._etag

    @handle_http_exceptions
    def prep_task(self, input_payload) -> bool:
        self._debug(f"TopazGen.prep_task({input_payload})")
        super().prep_task(input_payload=input_payload)

        source_ = get_video_source(input_payload['input'])
        filters_ = [{"model": "slf-3"}]
        output_ = {
            "resolution": { "width": 1920, "height": 1080 }, 
            "frameRate": source_["frameRate"],
            "videoEncoder": "H265",
            "container": "mp4",
            "audioTransfer": "None",
        }

        self._debug(f"prep_task source: {source_}")
        self._debug(f"prep_task filters: {filters_}")
        self._debug(f"prep_task output: {output_}")

        self._video_request = {
          "source": source_, 
          "filters": filters_, 
          "output": output_, 
        }

        import pprint
        pprint.pprint(self._video_request)
        pprint.pprint(self.JSON_HEADER)

        response = requests.post(TopazGen.API_SERVER, json=self._video_request, headers=self.JSON_HEADER)
        response.raise_for_status()
        if self._check_api_response(response):
            response_json = response.json()
            self._requestId = response_json['requestId']
            self._estimates = response_json['estimates']
        else:
            return None

        self._debug(f"prep_task upload requestId: {self._requestId}")
        self._debug(f"prep_task upload estimates: {self._estimates}")

        response = requests.patch(TopazGen.ACCEPT_URL.format(REQUEST_ID=self._requestId), headers=self.ACCEPT_HEADER)
        response.raise_for_status()
        if self._check_api_response(response):
            response_json = response.json()
            self._upload_urls = response_json['urls']
            assert(len(self._upload_urls) == 1) # dont support split uploads
            self._upload_id = response_json['uploadId']
        else:
            return None

        self._debug(f"prep_task upload urls: {self._upload_urls}")
        self._debug(f"prep_task upload uploadId: {self._upload_id}")

        self._etag = self.upload_file(input_payload['input'])
        if not self._etag:
            self._error(f"Upload failed for {input_payload['input']}")
            return None

        return True

    @handle_http_exceptions
    def submit_task(self) -> str:
        self._debug(f"TopazGen.submit_task()")

        if super().submit_task(): # check we haven't already sub'd this task/request
            pass # not sure how pythonic this is
        else:

            if self._etag:

                complete = {"uploadResults": [{"partNum": 1, "eTag": self._etag}]}
                print(complete)
                print(TopazGen.COMPLETE_URL.format(REQUEST_ID=self._requestId))
                response = requests.patch(
                    TopazGen.COMPLETE_URL.format(REQUEST_ID=self._requestId),
                    headers=self.HEADER,
                    json=complete
                )

                response.raise_for_status()

                self._task_id = self._requestId # task id is request id once job is correctly sub'd

                return self._task_id

