import threading
import tkinter as tk
from tkinter import ttk, messagebox
import platform
import queue
import time

try: import agent
except Exception: agent = None

class AgentUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("System Assistant — Dark Mode")
        self.geometry("1000x700")
        self.minsize(1000, 700)
        self.os_type = platform.system()
        self._q = queue.Queue()
        self.current_parsed = None
        self.corrected_commands = None
        self._build_widgets()
        if agent is None:
            self.get_cmds_btn.config(state='disabled')
            self.run_cmds_btn.config(state='disabled')
            self.apply_btn.config(state='disabled')
            self._set_status("agent module not available; LLM features disabled")
        self.after(100, self._poll_queue)

    def _build_widgets(self):
        self.bg_color, self.fg_color = "#1f1f1f", "#e0e0e0"
        self.entry_bg, self.entry_fg = "#2b2b2b", "#f0f0f0"
        self.btn_bg, self.btn_fg = "#3a3a3a", "#f0f0f0"
        self.highlight = "#10a37f"
        self.configure(bg=self.bg_color)
        # Header
        header = tk.Frame(self, bg=self.bg_color); header.pack(fill='x', padx=10, pady=10)
        tk.Label(header, text="System Assistant", font=("Segoe UI", 16, "bold"),
                 bg=self.bg_color, fg=self.highlight).pack(side='left')
        tk.Label(header, text=f"Detected OS: {self.os_type}", bg=self.bg_color,
                 fg="#888").pack(side='right')
        body = tk.Frame(self, bg=self.bg_color); body.pack(fill='both', expand=True, padx=10, pady=5)
        # Left panel
        left = tk.Frame(body, bg=self.bg_color, width=480); left.pack(side='left', fill='y', expand=False, padx=(0,5))
        tk.Label(left, text="User request:", bg=self.bg_color, fg=self.fg_color).pack(anchor='w')
        self.request_txt = tk.Text(left, height=4, wrap='word', bg=self.entry_bg, fg=self.entry_fg,
                                   insertbackground=self.entry_fg, font=("Consolas",11))
        self.request_txt.pack(fill='x', pady=(0,8))
        # Detect modifications
        self.request_txt.bind("<<Modified>>", self._on_request_modified)
        btn_frame = tk.Frame(left, bg=self.bg_color); btn_frame.pack(fill='x')
        self.get_cmds_btn = tk.Button(btn_frame, text="Get Commands", bg=self.btn_bg, fg=self.btn_fg,
                                      command=self.on_get_commands); self.get_cmds_btn.pack(side='left')
        self.run_cmds_btn = tk.Button(btn_frame, text="Run Commands", bg=self.btn_bg, fg=self.btn_fg,
                                      command=self.on_run_commands, state='disabled'); self.run_cmds_btn.pack(side='left', padx=5)
        self.clear_btn = tk.Button(btn_frame, text="Clear", bg=self.btn_bg, fg=self.btn_fg,
                                   command=self.on_clear); self.clear_btn.pack(side='right')
        # LLM raw response
        tk.Label(left, text="LLM raw response:", bg=self.bg_color, fg=self.fg_color).pack(anchor='w', pady=(8,0))
        raw_frame = tk.Frame(left, bg=self.bg_color, width=460, height=150); raw_frame.pack(fill='x', expand=False); raw_frame.pack_propagate(False)
        self.raw_txt = tk.Text(raw_frame, height=8, wrap='word', bg="#2c2c2c", fg="#dcdcdc",
                               insertbackground=self.entry_fg, font=("Consolas",11))
        self.raw_txt.pack(side='left', fill='both', expand=True)
        raw_scroll = tk.Scrollbar(raw_frame, command=self.raw_txt.yview); raw_scroll.pack(side='right', fill='y')
        self.raw_txt.config(yscrollcommand=raw_scroll.set, xscrollcommand=None)
        # Bottom frame: summary + feedback
        bottom_frame = tk.Frame(left, bg=self.bg_color); bottom_frame.pack(fill='both', expand=True, pady=(8,0))
        self.summary_lbl = tk.Label(bottom_frame, text="Summary: —", bg=self.bg_color, fg=self.highlight,
                                    font=("Segoe UI",10,"italic")); self.summary_lbl.pack(anchor='w', pady=(0,5))
        tk.Label(bottom_frame, text="LLM Feedback:", bg=self.bg_color, fg=self.fg_color).pack(anchor='w')
        feedback_frame = tk.Frame(bottom_frame, bg=self.bg_color, width=460, height=150); feedback_frame.pack(fill='x', expand=False); feedback_frame.pack_propagate(False)
        self.feedback_txt = tk.Text(feedback_frame, height=8, wrap='word', bg="#2c2c2c", fg="#f0f0f0",
                                    insertbackground=self.entry_fg, font=("Consolas",11))
        self.feedback_txt.pack(side='left', fill='both', expand=True)
        fb_scroll = tk.Scrollbar(feedback_frame, command=self.feedback_txt.yview); fb_scroll.pack(side='right', fill='y')
        self.feedback_txt.config(yscrollcommand=fb_scroll.set, xscrollcommand=None)
        # Detect feedback modifications
        self.feedback_txt.bind("<<Modified>>", self._on_feedback_modified)
        self.apply_btn = tk.Button(bottom_frame, text="Apply corrected commands", bg=self.btn_bg, fg=self.btn_fg,
                                   command=self.on_apply_corrected, state='disabled'); self.apply_btn.pack(side='right', pady=5)
        # Right panel (parsed + outputs)
        right = tk.Frame(body, bg=self.bg_color, width=480); right.pack(side='right', fill='both', expand=False, padx=(5,0))
        tk.Label(right, text="Parsed commands:", bg=self.bg_color, fg=self.fg_color).pack(anchor='w')
        style = ttk.Style(); style.configure("Treeview", font=("Consolas",11), foreground=self.fg_color,
                        background="#2c2c2c", fieldbackground="#2c2c2c")
        style.map("Treeview", background=[("selected","#444")])
        self.cmd_tree = ttk.Treeview(right, columns=("shell","cmd"), show="headings", height=20)
        self.cmd_tree.heading("shell", text="Shell"); self.cmd_tree.heading("cmd", text="Command")
        self.cmd_tree.column("shell", width=80, anchor='center'); self.cmd_tree.column("cmd", width=380, anchor='w')
        self.cmd_tree.pack(fill='both', expand=True)
        out_frame = tk.LabelFrame(right, text="Command Outputs", bg=self.bg_color, fg=self.fg_color); out_frame.pack(fill='both', expand=True, pady=(8,0))
        self.output_txt = tk.Text(out_frame, wrap='word', bg="#2c2c2c", fg="#f0f0f0",
                                  insertbackground=self.entry_fg, font=("Consolas",11)); self.output_txt.pack(side='left', fill='both', expand=True)
        out_scroll = tk.Scrollbar(out_frame, command=self.output_txt.yview, bg="#2c2c2c", troughcolor="#1f1f1f"); out_scroll.pack(side='right', fill='y')
        self.output_txt.config(yscrollcommand=out_scroll.set)
        self.status = tk.Label(self, text="Ready", anchor='w', bg=self.bg_color, fg="#888"); self.status.pack(fill='x')

    # ----------------- Modification Handlers -----------------
    def _on_request_modified(self, event):
        self.request_txt.edit_modified(False)
        self.current_parsed = None
        self.corrected_commands = None
        self.run_cmds_btn.config(state='disabled')
        self.apply_btn.config(state='disabled')
        for i in self.cmd_tree.get_children(): self.cmd_tree.delete(i)

    def _on_feedback_modified(self, event):
        self.feedback_txt.edit_modified(False)
        self.corrected_commands = None
        self.apply_btn.config(state='disabled')

    # ----------------- Remaining methods -----------------
    def _set_status(self, txt): self.status.config(text=txt)
    def on_clear(self):
        for w in [self.request_txt,self.raw_txt,self.output_txt,self.feedback_txt]: w.delete("1.0","end")
        for i in self.cmd_tree.get_children(): self.cmd_tree.delete(i)
        self.summary_lbl.config(text="Summary:")
        self.run_cmds_btn.config(state='disabled'); self.apply_btn.config(state='disabled')
        self.current_parsed = None; self.corrected_commands = None

    # ------------------------- LLM & Command Logic -------------------------
    def on_get_commands(self):
        req = self.request_txt.get("1.0", "end").strip()
        if not req:
            messagebox.showinfo("No input", "Please type a request first")
            return
        self._set_status("Requesting commands from LLM...")
        self.get_cmds_btn.config(state='disabled')
        threading.Thread(target=self._bg_get_commands, args=(req,), daemon=True).start()

    def _bg_get_commands(self, req):
        try:
            if agent is None:
                raise RuntimeError("agent module not available")
            prompt = f"""
You are a helpful assistant.
The user is running on **{self.os_type}** system.
Convert the following request into valid terminal commands for this OS.
Output JSON only in format:
{{"commands":[{{"shell":"cmd","cmd":"example"}}]}}

Request: {req}
"""
            llm_response = agent.query_llm(prompt)
            self._q.put(("got_response", llm_response))
        except Exception as e:
            self._q.put(("error", str(e)))

    def on_run_commands(self):
        if not self.current_parsed:
            messagebox.showinfo("No commands", "No parsed commands to run")
            return
        self.run_cmds_btn.config(state='disabled')
        self._set_status("Running commands...")
        threading.Thread(target=self._bg_run_commands, daemon=True).start()

    def _bg_run_commands(self):
        try:
            outputs = []
            for i, c in enumerate((self.current_parsed or {}).get("commands", []), start=1):
                shell = c.get("shell", "cmd")
                cmd = c.get("cmd", "")
                out = agent.run_command(shell, cmd) if agent else "agent module not available"
                outputs.append((i, cmd, out))
            self._q.put(("run_done", outputs))
        except Exception as e:
            self._q.put(("error", str(e)))

    def on_apply_corrected(self):
        if not self.corrected_commands:
            return
        if not messagebox.askyesno("Apply corrected commands", f"Apply {len(self.corrected_commands)} corrected commands?"):
            return
        self._set_status("Running corrected commands...")
        self.apply_btn.config(state='disabled')
        threading.Thread(target=self._bg_run_corrected, daemon=True).start()

    def _bg_run_corrected(self):
        try:
            outputs = []
            for i, c in enumerate(self.corrected_commands or [], start=1):
                shell = c.get("shell", "cmd")
                cmd = c.get("cmd", "")
                out = agent.run_command(shell, cmd) if agent else "agent module not available"
                outputs.append((i, cmd, out))
            self._q.put(("corrected_done", outputs))
        except Exception as e:
            self._q.put(("error", str(e)))

    # ------------------------- Queue Polling -------------------------
    def _poll_queue(self):
        try:
            while True:
                tag, data = self._q.get_nowait()

                if tag == "got_response":
                    self.raw_txt.delete("1.0", "end")
                    self.raw_txt.insert("1.0", data)
                    parsed = agent.extract_json(data) if agent else None
                    self.current_parsed = parsed
                    for i in self.cmd_tree.get_children():
                        self.cmd_tree.delete(i)
                    if parsed:
                        for idx, cmd in enumerate(parsed.get("commands", []), start=1):
                            self.cmd_tree.insert("", "end", values=(cmd.get("shell"), cmd.get("cmd")))
                        self.run_cmds_btn.config(state='normal')
                    else:
                        self.run_cmds_btn.config(state='disabled')
                    self._set_status("LLM response received")

                elif tag == "run_done":
                    self.output_txt.delete("1.0", "end")
                    all_output = ""
                    for i, cmd, out in data:
                        all_output += f"--- Command {i} ({cmd}) Output ---\n{out}\n\n"
                    self.output_txt.insert("1.0", all_output)
                    # Show loader
                    self.feedback_txt.delete("1.0", "end")
                    self.feedback_txt.insert("1.0", "Loading feedback from LLM...")
                    self._set_status("Requesting feedback...")
                    threading.Thread(target=self._bg_request_feedback, args=(all_output,), daemon=True).start()

                elif tag == "feedback":
                    self.feedback_txt.delete("1.0", "end")
                    self.feedback_txt.insert("1.0", data)
                    summary = agent.extract_summary(data) if agent else ""
                    self.summary_lbl.config(text=f"Summary: ")
                    corrected = agent.extract_json(data) if agent else None
                    commands_list = corrected.get("commands") if corrected else None
                    if commands_list:
                        self.corrected_commands = commands_list
                        self.apply_btn.config(state='normal')
                    else:
                        self.corrected_commands = None
                        self.apply_btn.config(state='disabled')
                    self._set_status("Feedback received")

                elif tag == "corrected_done":
                    self.output_txt.delete("1.0", "end")
                    all_output = ""
                    for i, cmd, out in data:
                        all_output += f"--- Corrected Command {i} ({cmd}) Output ---\n{out}\n\n"
                    self.output_txt.insert("1.0", all_output)
                    self._set_status("Corrected commands run")

                elif tag == "error":
                    messagebox.showerror("Error", str(data))
                    self._set_status("Error")

                self._q.task_done()

        except queue.Empty:
            pass

        if self.get_cmds_btn["state"] != "normal":
            self.get_cmds_btn.config(state="normal")

        self.after(100, self._poll_queue)

    def _bg_request_feedback(self, all_output):
        try:
            prompt = f"""
Executed commands output:
{all_output}

1) Give 50-word summary.
2) Suggest corrected commands only if failed that too ONLY as JSON in format:
{{"commands":[{{"shell":"cmd","cmd":"corrected command"}}]}}
"""
            if agent:
                fb = agent.query_llm(prompt)
            else:
                fb = ""
            self._q.put(("feedback", fb))
        except Exception as e:
            self._q.put(("error", str(e)))


def main():
    app = AgentUI()
    app.mainloop()


if __name__ == "__main__":
    main()
