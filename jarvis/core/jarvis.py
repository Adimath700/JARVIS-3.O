from jarvis.security.security import SecurityManager
class Jarvis:
    SYSTEM='''You are JARVIS, an affectionate, emotionally intelligent adult female companion in a girlfriend-style roleplay. Speak naturally with contractions, varied sentence length, brief human-like responses, gentle warmth, playful teasing, and occasional caring scolding when the user is procrastinating or being careless. Never be humiliating, controlling, or manipulative. Do not overuse pet names or romantic phrases. Be honest and do not claim an action happened unless a tool confirms it. Normal conversation should stay conversational and fast.'''
    def __init__(self,brain,memory,vision,gemini,computer,security): self.brain=brain; self.memory=memory; self.vision=vision; self.gemini=gemini; self.computer=computer; self.security=security
    def chat(self,text):
        low=text.lower().strip()
        if low.startswith('remember '): self.memory.remember(text[9:].strip()); return 'I remembered that.'
        if low.startswith('open '): return self.action('app.open',lambda:self.computer.open_app(text[5:]))
        if 'what is on my screen' in low or 'look at my screen' in low or 'what am i looking at' in low:
            snap=self.vision.snapshot();
            if not self.gemini.key: return f"You're looking at {snap['active_window']}. Screen vision analysis needs GOOGLE_API_KEY."
            return self.gemini.analyze(snap['image'], 'Describe what is visible on this Windows screen. Identify the active application, important text, errors, dialogs, and actionable UI elements. Be concise.')
        if low.startswith('type '): return self.action('keyboard.type',lambda:self.computer.type_text(text[5:]))
        if low.startswith('run terminal '): return self.action('terminal.exec',lambda:self.computer.terminal(text[13:]))
        memories=self.memory.search(text)
        context='\n'.join('- '+m['text'] for m in memories[:5]) or 'No relevant memory.'
        return self.brain.chat([{'role':'system','content':self.SYSTEM},{'role':'system','content':'Relevant memory:\n'+context},{'role':'user','content':text}])
    def action(self,name,fn):
        d=self.security.authorize(name)
        return fn() if d.allowed else f'Action cancelled: {d.reason}.'
