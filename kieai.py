

from . import GenAPI
from . import handle_http_exceptions

class KieAIGen(GenAPI):
    """Subclass now stays lightweight—containing only API constants and headers."""
    API_SERVER = "https://api.kie.ai"
    BASE_API_URL = f"{API_SERVER}/api/v1"
    CREATE_TASK_URL = f"{BASE_API_URL}/jobs/createTask"
    QUERY_TASK_URL = f"{BASE_API_URL}/jobs/recordInfo"
    UPLOAD_URL = f"{BASE_API_URL}/file-stream-upload"

    def __init__(self, api_key, output_basepath, task_id=None, path_converter_func=lambda x: x):
        super().__init__(output_basepath, task_id=task_id, path_converter_func=path_converter_func)
        self._api_key = api_key
        self._auth_header = {"Authorization": f"Bearer {self._api_key}"}
        self._json_header = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }


class KieAIVideoGen(KieAIGen):
    """
    Base class for kie.ai video gen api
    """

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
            response = requests.post(KieAIGen.CREATE_TASK_URL, json=task_payload, headers=self._json_header)
            response.raise_for_status()
            if self._check_api_response(response):
                response_json = response.json()
                self._task_id = response_json['data']['taskId']
                return self._task_id
        return None

    @handle_http_exceptions
    def _query_task(self):
        self._debug(f"KieAIVideoGen._query_task()")
        response = requests.get(f"{KieAIGen.QUERY_TASK_URL}?taskId={self._task_id}", headers=self._auth_header)
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
        assert (isinstance(task_status, self.TASK_STATUS))
        if task_status in [self.TASK_STATUS.generating, self.TASK_STATUS.waiting, self.TASK_STATUS.queuing]:
            return False
        return True

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
        super().__init__(api_key=api_key, output_basepath=output_basepath, task_id=task_id,
                         path_converter_func=path_converter_func)
        self._debug(f"KieAIVideoGen_Veo({api_key}, task_id={task_id}, fullhd={fullhd})")
        self._fullhd = fullhd

    def _check_api_response(self, response):
        # handle veo specific responses
        self._debug(f"KieAIVideoGen_Veo._check_api_response({response})")
        response_json = response.json()
        if response_json['code'] == 400 and self._fullhd:  # 1080P is still processing
            self._info("1080P is processing. It should be ready in 1-2 minutes. Please check back shortly.")
            return True
        elif response_json['code'] == 422 and "generate" in response_json[
            'msg'].lower():  # fullhd sometimes returns 422 "Records are being generated"
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
        if gen_payload['generationType'] != "TEXT_2_VIDEO" and not 'images' in gen_payload:
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
            url = f"{KieAIVideoGen._base_api_url}/veo/record-info?taskId={self._task_id}"  # wait for the default version
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
            return query_task_response['data']['response'][
                'resultUrls']  # is it resultUrls or result_urls ?? not HD so we may never know :)


def kie_factory(payload, api_key, output_basepath, task_id=None, path_converter_func=lambda x: x):
    if 'veo' in payload['model'].lower():
        # google veo has it's own api

        # 1080P needs to be explicitly used if required
        fullhd = False
        if 'fullhd' in payload and payload['fullhd']:
            fullhd = True

        # connect to existing task or start a new one
        kie = KieAIVideoGen_Veo(api_key, output_basepath=output_basepath, task_id=task_id, fullhd=fullhd,
                                path_converter_func=path_converter_func)
    else:
        # assume it is the create/query api
        kie = KieAIVideoGen(api_key, output_basepath=output_basepath, task_id=task_id,
                            path_converter_func=path_converter_func)
    return kie