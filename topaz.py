import os
import requests
import re
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
    REQUEST_URL =   API_SERVER+"{REQUEST_ID}"
    ACCEPT_URL =    REQUEST_URL+"/accept"
    COMPLETE_URL =  REQUEST_URL+"/complete-upload/"
    STATUS_URL =    REQUEST_URL+"/status"
    HISTORY_URL =   API_SERVER+"history"
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

    @property
    def num_filters(self):
        return len(self._video_request["filters"])

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

    def _upload_file(self, path: str | Path):

        if self._upload_urls:

            with open(path, "rb") as f:
                put = requests.put(self._upload_urls[0], data=f.read())

            put.raise_for_status()

            # print(put.headers)
            if "ETag" in put.headers:
                self._etag = put.headers["ETag"].strip('"')
                return self._etag

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
        elif "requested" in task_response_status.lower() or "accepted" in task_response_status.lower():
            return self.TASK_STATUS.waiting
            #return self.TASK_STATUS.queuing
        else:
            return self.TASK_STATUS.unknown

    def _get_task_message(self, query_task_response):
        self._debug(f"TopazGen._get_task_message({query_task_response})")
        return query_task_response['message']

    @handle_http_exceptions
    def get_request_history(self):
        """
        Iterate over all current requests returning the request id and request stats in a tuple.
        """
        self._debug(f"TopazGen._get_request_history()")
        response = requests.get(TopazGen.HISTORY_URL, headers=self.HEADER)
        response.raise_for_status()
        if self._check_api_response(response):
            response_json = response.json()
            for request in response_json["result"]:
                yield(request["id"], request["status"], )

    @handle_http_exceptions
    def cancel_request(self, request_id):
        """
        Cancel the request with the given request_id.
        """
        response = requests.delete(TopazGen.REQUEST_URL.format(REQUEST_ID=request_id), headers=self.HEADER)
        response.raise_for_status()
        return response

    def cancel_requests(self, cancel_status="accepted"):
        """
        Cancel all requests with status matching cancel_status.
        Topaz reserves credits for accepted requests, this function cancels any found freeing up credits.
        Args:
            cancel_status: status to match for canceling requests

        Returns:
            Number of requests canceled.
        """
        self._debug(f"TopazGen._cancel_requests()")

        canceled_requests = 0
        for request_id, status in self.get_request_history():
            if cancel_status in status:
                self._info(f"Cancelling request {request_id} with status {status}")
                self.cancel_request(request_id)
                canceled_requests += 1

        return canceled_requests




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
            return (self._get_task_status(response_json), self._get_task_message(response_json), response_json)
        return (None, None, None)

    @handle_http_exceptions
    def prep_task(self, input_payload) -> bool:
        self._debug(f"TopazGen.prep_task({input_payload})")
        super().prep_task(input_payload=input_payload)


        filters = {}
        source = None
        output_width = -1
        output_height = -1
        for param in input_payload:

            if param == "input":
                source = get_video_source(input_payload['input'])

            elif param == "output_width":
                output_width = input_payload[param]

            elif param == "output_height":
                output_height = input_payload[param]

            elif m := re.match(r"filter(\d+)_(.*)", param):
                filter_id = int(m.group(1))
                filter_param = m.group(2)
                filters.setdefault(filter_id, {})[filter_param] = input_payload[param]

            else:
                self._warning(f"Orphan param found in the payload \"{param}\" - note that filter params need a filter prefix for Topaz")

        if not source:
            self._error(f"No input/source found in payload {input_payload}")
            return

        if not filters:
            self._error(f"No filters found in payload {input_payload}")
            return



        output_ = {
            "resolution": {
                "width": output_width if output_width > 0 else source["resolution"]["width"],
                "height": output_height if output_height > 0 else source["resolution"]["height"],
            },
            "frameRate": source["frameRate"],
            "videoEncoder": "H265",
            "container": "mp4",
            "audioTransfer": "None",
        }

        self._debug(f"prep_task source: {source}")
        self._debug(f"prep_task filters dict: {filters}")
        self._debug(f"prep_task output: {output_}")

        self._video_request = {
          "source": source,
          "filters": [filters[fid] for fid in sorted(filters)], # order the filters based on their id
          "output": output_, 
        }

        self._debug(f"prep_task filters list: {self._video_request["filters"]}")

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

        self._debug(f"Upload etag: {self._etag}")

        return True

    @handle_http_exceptions
    def submit_task(self, test=False) -> str:
        self._debug(f"TopazGen.submit_task()")

        if super().submit_task(): # check we haven't already sub'd this task/request
            pass # not sure how pythonic this is
        else:

            if test:
                # test run, cancel the request
                self._debug(f"Test run canceling request {self._requestId}")
                self.cancel_request(self._requestId)

            elif self._etag:

                # upload complete notification begins the task
                complete = {"uploadResults": [{"partNum": 1, "eTag": self._etag}]}
                response = requests.patch(
                    TopazGen.COMPLETE_URL.format(REQUEST_ID=self._requestId),
                    headers=self.HEADER,
                    json=complete
                )

                response.raise_for_status()

                self._task_id = self._requestId # task id is request id once job is correctly sub'd

                return self._task_id

