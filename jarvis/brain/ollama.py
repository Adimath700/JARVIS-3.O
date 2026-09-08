import requests


class OllamaBrain:
    def __init__(
        self,
        base_url,
        model,
        think=False,
        keep_alive="30m",
        num_predict=128,
        num_ctx=2048,
    ):
        self.url = base_url.rstrip("/") + "/api/chat"
        self.model = model
        self.think = think
        self.keep_alive = keep_alive
        self.num_predict = num_predict
        self.num_ctx = num_ctx

    def chat(self, messages, timeout=60):
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": self.think,
            "keep_alive": self.keep_alive,
            "options": {
                "num_ctx": self.num_ctx,
                "num_predict": self.num_predict,
            },
        }
        r = requests.post(self.url, json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()["message"]["content"]

    def warm_up(self):
        try:
            requests.post(
                self.url.rsplit("/api/", 1)[0] + "/api/generate",
                json={
                    "model": self.model,
                    "prompt": "",
                    "keep_alive": self.keep_alive,
                    "stream": False,
                },
                timeout=60,
            ).raise_for_status()
        except requests.RequestException:
            return False
        return True

    def available(self):
        try:
            return requests.get(
                self.url.rsplit("/api/", 1)[0] + "/api/tags", timeout=3
            ).ok
        except requests.RequestException:
            return False
