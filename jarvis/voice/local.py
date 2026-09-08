import tempfile, os, subprocess
class LocalVoice:
    def __init__(self,model='tiny.en',device='cpu',compute_type='int8',piper_exe='',piper_voice='en_US-lessac-medium'):
        self.model_name=model; self.device=device; self.compute_type=compute_type; self.piper_exe=piper_exe; self.piper_voice=piper_voice; self._model=None
    def listen(self):
        import sounddevice as sd, soundfile as sf
        from faster_whisper import WhisperModel
        if self._model is None: self._model=WhisperModel(self.model_name,device=self.device,compute_type=self.compute_type)
        print('🎤 Listening...')
        audio=sd.rec(int(6*16000),samplerate=16000,channels=1,dtype='float32'); sd.wait()
        with tempfile.NamedTemporaryFile(suffix='.wav',delete=False) as f: path=f.name
        sf.write(path,audio,16000)
        try:
            segments,_=self._model.transcribe(path,vad_filter=True,beam_size=3); return ' '.join(s.text.strip() for s in segments).strip()
        finally: os.unlink(path)
    def speak(self,text):
        if not self.piper_exe: print('JARVIS:',text); return
        subprocess.run([self.piper_exe,'--model',self.piper_voice,'--output_file','-'],input=text,text=True,stdout=subprocess.DEVNULL,check=False)
