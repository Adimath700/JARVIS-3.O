import sys, tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from jarvis.security.security import SecurityManager, Risk
from jarvis.memory.memory import Memory

def test_security():
    s=SecurityManager(Path(tempfile.mkdtemp())/'a.log'); assert s.classify('screen.capture')==Risk.LOW; assert s.classify('terminal.exec')==Risk.HIGH

def test_memory():
    p=Path(tempfile.mkdtemp())/'m.json'; m=Memory(p); m.remember('JARVIS test'); assert m.search('jarvis')
if __name__=='__main__': test_security(); test_memory(); print('PASS')
