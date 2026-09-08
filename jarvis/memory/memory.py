from pathlib import Path
import json, time
class Memory:
    def __init__(self,path:Path):
        self.path=path; self.path.parent.mkdir(parents=True,exist_ok=True)
        if not self.path.exists(): self.path.write_text('[]',encoding='utf-8')
    def remember(self,text:str):
        items=json.loads(self.path.read_text(encoding='utf-8')); items.append({'text':text,'time':time.time()}); self.path.write_text(json.dumps(items,indent=2),encoding='utf-8')
    def search(self,q:str,limit=8):
        ql=q.lower(); items=json.loads(self.path.read_text(encoding='utf-8'))
        return [x for x in reversed(items) if ql in x['text'].lower()][:limit]
