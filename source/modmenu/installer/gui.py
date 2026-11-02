"""Portuguese installer UI, hosted by the original setup's bundled Python/Tk."""
import argparse
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import uuid
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
from worker import install


class App:
    def __init__(self, root, payload, setup):
        self.root, self.payload = root, payload
        self.events, self.busy, self.receipt = queue.Queue(), False, None
        root.title('Instalar TotK Mod Menu 0.1.0-rc.1')
        root.geometry('780x560'); root.minsize(680, 480)
        root.protocol('WM_DELETE_WINDOW', self.close)
        frame = ttk.Frame(root, padding=20); frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Instalar Mod Menu', font=('Segoe UI', 18, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='Recomp 0.3.1 + jogo 1.4.3 | Sem substituir o jogo original').pack(anchor='w', pady=(3, 16))
        self.game, self.setup = tk.StringVar(), tk.StringVar(value=str(setup))
        self.controls = []
        for title, variable in (('Pasta do jogo instalado (contém totk.exe)', self.game),
                                ('Pasta do setup original (contém python e llvm)', self.setup)):
            ttk.Label(frame, text=title).pack(anchor='w')
            row = ttk.Frame(frame); row.pack(fill='x', pady=(3, 10))
            entry = ttk.Entry(row, textvariable=variable); entry.pack(side='left', fill='x', expand=True)
            button = ttk.Button(row, text='Procurar...', command=lambda v=variable: self.browse(v)); button.pack(side='right', padx=(8, 0))
            self.controls += [entry, button]
        ttk.Label(frame, text='O cache será localizado automaticamente. Salve e feche o jogo antes de continuar.\n'
                  'O instalador gera as miniaturas e compila o mod nesta máquina, sem downloads.').pack(anchor='w')
        self.progress = ttk.Progressbar(frame, mode='indeterminate'); self.progress.pack(fill='x', pady=12)
        self.text = tk.Text(frame, height=10, wrap='word', state='disabled', font=('Consolas', 9))
        self.text.pack(fill='both', expand=True)
        row = ttk.Frame(frame); row.pack(fill='x', pady=(12, 0))
        self.start = ttk.Button(row, text='Instalar Mod Menu', command=self.start_install); self.start.pack(side='left')
        self.open_button = ttk.Button(row, text='Abrir Mod Menu', state='disabled', command=self.open_game); self.open_button.pack(side='left', padx=8)
        ttk.Button(row, text='Fechar', command=self.close).pack(side='right')
        self.controls.append(self.start)
        root.after(100, self.poll)

    def browse(self, variable):
        result = filedialog.askdirectory(parent=self.root, mustexist=True)
        if result: variable.set(result)

    def start_install(self):
        if not self.game.get().strip():
            messagebox.showinfo('Selecione o jogo', 'Escolha a pasta do jogo já instalado.', parent=self.root); return
        self.busy = True; self.progress.start()
        for control in self.controls: control.configure(state='disabled')
        game, setup = self.game.get(), self.setup.get()
        def work():
            try:
                destination = Path(os.environ['LOCALAPPDATA']) / 'TotKModMenu/installations'
                logs = destination.parent / 'logs'; logs.mkdir(parents=True, exist_ok=True)
                log_path = logs / ('install-' + uuid.uuid4().hex[:12] + '.log')
                with log_path.open('w', encoding='utf-8') as output:
                    def log(message):
                        output.write(message + '\n'); output.flush()
                        self.events.put(('log', message))
                    log('Registro: ' + str(log_path))
                    receipt = install(self.payload, setup, game, destination, log)
                self.events.put(('done', receipt))
            except Exception as error:
                self.events.put(('error', str(error)))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == 'log':
                    self.text.configure(state='normal'); self.text.insert('end', data + '\n'); self.text.see('end'); self.text.configure(state='disabled')
                else:
                    self.busy = False; self.progress.stop()
                    for control in self.controls: control.configure(state='normal')
                    if kind == 'done':
                        self.receipt = data; self.open_button.configure(state='normal')
                        self.save_shortcut()
                        messagebox.showinfo('Instalação concluída', 'O Mod Menu está pronto. Use o botão Abrir Mod Menu ou o atalho na área de trabalho.\n\nF1 > Cheats > Adicionar itens.', parent=self.root)
                    else:
                        messagebox.showerror('Não foi possível instalar', data, parent=self.root)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def save_shortcut(self):
        target = str(Path(self.receipt['output']) / 'Abrir Mod Menu.cmd').replace("'", "''")
        script = "$w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'),'TotK Mod Menu.lnk')); $s.TargetPath='" + target + "'; $s.WorkingDirectory='" + str(Path(self.receipt['output'])).replace("'", "''") + "'; $s.Save()"
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            self.text.configure(state='normal'); self.text.insert('end', 'Atalho não criado. Use Abrir Mod Menu ou a pasta indicada no registro.\n'); self.text.configure(state='disabled')

    def open_game(self):
        os.startfile(str(Path(self.receipt['output']) / 'Abrir Mod Menu.cmd'))

    def close(self):
        if self.busy:
            messagebox.showinfo('Instalação em andamento', 'Aguarde a conclusão da compilação antes de fechar.', parent=self.root)
        else: self.root.destroy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--setup', type=Path, required=True)
    ap.add_argument('--selftest', action='store_true')
    args = ap.parse_args()
    root = tk.Tk()
    app = App(root, Path(__file__).resolve().parent, args.setup)
    if args.selftest:
        root.update()
        assert root.winfo_width() >= 680 and len(app.controls) == 5 and not app.busy
        root.destroy()
        print('INSTALLER_UI_CHECK_OK')
    else:
        root.mainloop()


if __name__ == '__main__':
    main()
