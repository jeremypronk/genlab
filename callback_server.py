from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.request
import threading
#from urllib.parse import urlparse, parse_qs
import json
import logging

class CallbackServer:
    class _Handler(BaseHTTPRequestHandler):
        callback_fn = None  # will be set by parent

        def do_POST(self):
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            post_json = json.loads(post_data.decode("utf-8"))

            if CallbackServer._Handler.callback_fn:
                try:
                    #parsed = urlparse(self.path)
                    #CallbackServer._Handler.callback_fn(self.path, self.headers, body)
                    CallbackServer._Handler.callback_fn(post_json)
                except Exception as e:
                    print("Error in callback function:", e)

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")

    def __init__(self, local_port=5000, external_port=6666, callback=None):
        self.local_port = local_port
        self.external_port = external_port or local_port
        CallbackServer._Handler.callback_fn = callback
        self._server = HTTPServer(("0.0.0.0", local_port), CallbackServer._Handler)
        self._thread = None

    def start(self):
        """Start the HTTP server in a background thread (non-blocking)."""
        if self._thread and self._thread.is_alive():
            return  # already running

        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the HTTP server."""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        if self._thread:
            self._thread.join()

    def get_public_ip(self):
        """Retrieve external IP address (WAN)."""
        try:
            with urllib.request.urlopen("https://api.ipify.org") as response:
                return response.read().decode()
        except Exception as e:
            print("Could not determine public IP:", e)
            return None

    def get_callback_url(self, path):
        """Return the full callback URL accessible from the internet."""
        ip = self.get_public_ip()
        if ip:
            return f"http://{ip}:{self.external_port}/{path}"
        return None

    def get_local_callback_url(self, path):
        """Return the local callback URL."""
        return f"http://127.0.0.1:{self.local_port}/{path}"


# --- Example usage ---
#curl -X POST "http://127.0.0.1:5001/callback?task_id=Jsakjf34*&output_path=x:/blahbutt" -d "hello=world"
if __name__ == "__main__":
    #def my_callback(path, headers, body):
    #def my_callback(path, args):
    def download_video_callback(post_json):
        logging.debug(f"download_video_callback({post_json})")
        logging.info(post_json['msg'])

        if post_json['code'] != 200:
            logging.error(f"Generation failed cannot download! Return code: {post_json['code']}")
            return

        logging.info(f"Downloading video for {post_json['data']['taskId']}")


    log_level = logging.DEBUG
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    server = CallbackServer(local_port=5001, external_port=6666, callback=download_video_callback)

    server.start()  # non-blocking
    print("Public callback URL:", server.get_callback_url("callback"))
    print("Local test URL: http://127.0.0.1:5001/callback")

    # Main program continues running
    import time
    try:
        while True:
            print("Main program is free to do other work...")
            time.sleep(5)
    except KeyboardInterrupt:
        print("Shutting down server...")
        server.stop()

"""
curl -X POST "http://127.0.0.1:5001/callback" \
  -H "Content-Type: application/json" \
  -d '{
    "code": 200,
    "data": {
        "completeTime": 1755599644000,
        "consumeCredits": 100,
        "costTime": 8,
        "createTime": 1755599634000,
        "model": "bytedance/v1-pro-image-to-video",
        "param": "{\"callBackUrl\":\"https://your-domain.com/api/callback\",\"model\":\"bytedance/v1-pro-image-to-video\",\"input\":{\"prompt\":\"A golden retriever dashing through shallow surf at the beach, back angle camera low near waterline, splashes frozen in time, blur trails in waves and paws, afternoon sun glinting off wet fur, overcast day, dramatic clouds\",\"image_url\":\"https://file.aiquickdraw.com/custom-page/akr/section-images/1755179021328w1nhip18.webp\",\"resolution\":\"720p\",\"duration\":\"5\",\"camera_fixed\":false,\"seed\":-1,\"enable_safety_checker\":true}}",
        "remainedCredits": 2510330,
        "resultJson": "{\"resultUrls\":[\"https://example.com/generated-image.jpg\"]}",
        "state": "success",
        "taskId": "e989621f54392584b05867f87b160672",
        "updateTime": 1755599644000
    },
    "msg": "Playground task completed successfully."
}'


curl -X POST "http://127.0.0.1:5001/callback" \
  -H "Content-Type: application/json" \
  -d '{
    "code": 501,
    "data": {
        "completeTime": 1755597081000,
        "consumeCredits": 0,
        "costTime": 0,
        "createTime": 1755596341000,
        "failCode": "500",
        "failMsg": "Internal server error",
        "model": "bytedance/v1-pro-image-to-video",
        "state": "fail",
        "taskId": "bd3a37c523149e4adf45a3ddb5faf1a8",
        "updateTime": 1755597097000
    },
    "msg": "Playground task failed."
}'


Invoke-RestMethod -Uri "http://127.0.0.1:5001/callback" `
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
        "resultJson": "{\"resultUrls\":[\"https://example.com/generated-image.jpg\"]}",
        "state": "success",
        "taskId": "b157d2585ffe4b67acd264e627532edb",
        "updateTime": 1755599644000
    },
    "msg": "Playground task completed successfully."
}'



"""