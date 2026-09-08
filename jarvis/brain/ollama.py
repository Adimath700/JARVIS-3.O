import requests
class OllamaBrain:
    def __init__(self,base_url,model): self.url=base_url.rstrip('/')+'/api/chat'; self.model=model
    def chat(self,messages,timeout=90):
        r=requests.post(self.url,json={'model':self.model,'messages':messages,'stream':False},timeout=timeout); r.raise_for_status(); return r.json()['message']['content']
    def available(self):
        try: return requests.get(self.url.rsplit('/api/',1)[0]+'/api/tags',timeout=3).ok
        except requests.RequestException: return False
