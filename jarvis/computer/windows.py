import os, subprocess, shutil

class WindowsComputer:
    def _start_menu_app_id(self, query: str):
        if os.name != 'nt': return None
        ps = "Get-StartApps | ConvertTo-Json -Compress"
        try:
            raw = subprocess.check_output(['powershell','-NoProfile','-Command',ps],text=True,timeout=8,creationflags=subprocess.CREATE_NO_WINDOW)
            import json
            rows=json.loads(raw) if raw.strip() else []
            if isinstance(rows,dict): rows=[rows]
            q=query.lower()
            exact=next((r for r in rows if str(r.get('Name','')).lower()==q),None)
            row=exact or next((r for r in rows if q in str(r.get('Name','')).lower()),None)
            return row.get('AppID') if row else None
        except Exception:
            return None

    def open_app(self,name):
        name=name.strip()
        aliases={'vs code':'Visual Studio Code','visual studio code':'Visual Studio Code','chrome':'Google Chrome','google chrome':'Google Chrome','notepad':'Notepad','calculator':'Calculator','whatsapp':'WhatsApp','discord':'Discord','edge':'Microsoft Edge','file explorer':'File Explorer'}
        display=aliases.get(name.lower(),name)
        app_id=self._start_menu_app_id(display)
        if app_id:
            subprocess.Popen(['explorer.exe',f'shell:AppsFolder\\{app_id}'],creationflags=subprocess.CREATE_NO_WINDOW)
            return f'Opening {display}.'
        # Win32 aliases/executables for classic applications.
        exe_alias={'notepad':'notepad.exe','calculator':'calc.exe','file explorer':'explorer.exe','chrome':'chrome.exe','google chrome':'chrome.exe','edge':'msedge.exe','vs code':'code.cmd','visual studio code':'code.cmd'}
        exe=exe_alias.get(name.lower(),name)
        try:
            path=shutil.which(exe)
            if path: subprocess.Popen([path]); return f'Opening {display}.'
        except Exception: pass
        try:
            os.startfile(exe)
            return f'Opening {display}.'
        except Exception:
            return f'I could not find {display} in the Windows Start Apps catalog.'

    def terminal(self,command):
        return subprocess.run(command,shell=True,capture_output=True,text=True,timeout=30).stdout[-6000:]
    def type_text(self,text):
        import pyautogui; pyautogui.write(text,interval=0.01); return 'Text typed.'
    def press(self,key):
        import pyautogui; pyautogui.press(key); return f'Pressed {key}.'
