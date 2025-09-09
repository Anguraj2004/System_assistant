import subprocess
import json
import platform
import shutil
import html
import re
import os
from typing import List, Optional
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)
conversation_history = []

def query_llm(prompt: str) -> str:
    global conversation_history
    try:
        # Append system and user messages
        conversation_history.append({"role": "system","content": "You are agent who converts requests to valid shell commands based on the OS running."})
        conversation_history.append({"role": "user", "content": prompt})

        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=conversation_history,
            temperature=1,
            max_completion_tokens=1024,
            top_p=1,
            stream=False,
            stop=None
        )
        llm_output = completion.choices[0].message.content or ""
        conversation_history.append({"role": "assistant", "content": llm_output})
        if len(conversation_history) > 40:
            conversation_history = conversation_history[-40:]
        return llm_output
    except Exception as e:
        return f"LLM error: {str(e)}"

def run_command(shell, cmd):
    try:
        sh = (shell or "cmd").lower()
        if sh in ("powershell", "pwsh"):
            pwsh_exec = shutil.which("pwsh") or shutil.which("powershell")
            if not pwsh_exec:
                return "PowerShell executable not found"
            args = [pwsh_exec, "-NoProfile", "-NonInteractive", "-Command", cmd]
            completed = subprocess.run(args, capture_output=True, text=True)
        elif sh == "cmd":
            args = ["cmd", "/c", cmd]
            completed = subprocess.run(args, capture_output=True, text=True)
        else:
            completed = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return completed.stdout if completed.returncode == 0 else completed.stderr
    except Exception as e:
        return str(e)

def extract_json(text) -> Optional[dict]:
    def _candidates_from_fences(t: str) -> List[str]:
        return [m.group(1).strip() for m in re.finditer(r"```(?:json)?\n(.*?)```", t, re.DOTALL|re.IGNORECASE)]
    def _balanced_brace_candidates(t: str) -> List[str]:
        candidates = []
        for i, ch in enumerate(t):
            if ch == '{':
                stack = 1
                j = i + 1
                while j < len(t) and stack > 0:
                    if t[j] == '{': stack += 1
                    elif t[j] == '}': stack -= 1
                    j += 1
                if stack == 0: candidates.append(t[i:j])
        return candidates
    def _try_parse(s: str) -> Optional[object]:
        s = html.unescape(s.strip())
        try: return json.loads(s)
        except json.JSONDecodeError:
            s_fixed = re.sub(r",\s*}\s*$", "}", s)
            s_fixed = re.sub(r",\s*\]\s*$", "]", s_fixed)
            s_fixed = s_fixed.replace('\\', '\\\\')
            if s_fixed.count("'") > s_fixed.count('"'): s_fixed = s_fixed.replace("'", '"')
            try: return json.loads(s_fixed)
            except json.JSONDecodeError: return None
    try:
        parsed_whole = json.loads(text)
        if isinstance(parsed_whole, dict): return parsed_whole
    except json.JSONDecodeError: pass
    candidates = _candidates_from_fences(text) or _balanced_brace_candidates(text)
    for cand in candidates:
        parsed = _try_parse(cand)
        if isinstance(parsed, dict): return parsed
    return None

def _strip_markdown(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*|__|\*|_", "", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^>\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def extract_summary(text: str, max_words: int = 50) -> str:
    if not text: return ""
    m = re.search(r"(?is)\*\*Summary\*\*\s*[:\-]?\s*(.+?)(?:\n\n|$)", text) or \
        re.search(r"(?is)^Summary\s*[:\-]?\s*(.+?)(?:\n\n|$)", text)
    summary = _strip_markdown(m.group(1)) if m else _strip_markdown(text)
    words = summary.split()
    return " ".join(words[:max_words]) + (" …" if len(words) > max_words else "")
