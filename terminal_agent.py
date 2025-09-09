import subprocess
import json
import platform
import uuid
import os
import re
import shutil
import html
from typing import List, Optional
from dotenv import load_dotenv
from groq import Groq

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)

# Global conversation ID and history
conversation_id = None
conversation_history = []

def query_llm(prompt: str) -> str:
    """Send a prompt to the LLM and return the assistant content.

    Keeps conversation history but caps it to avoid unbounded growth.
    Returns a short error string on failure.
    """
    global conversation_history
    try:
        # Append user prompt to history
        conversation_history.append({"role": "system","content": "You are agent who converts requests to valid shell commands based on the OS running "})
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

        # Extract response content (coerce None to empty string)
        llm_output = completion.choices[0].message.content
        if llm_output is None:
            llm_output = ""
        else:
            llm_output = str(llm_output)

        # Update history and cap it to the last 20 messages
        conversation_history.append({"role": "assistant", "content": llm_output})
        if len(conversation_history) > 40:
            conversation_history = conversation_history[-40:]

        return llm_output
    except Exception as e:
        return f"LLM error: {str(e)}"

def run_command(shell, cmd):
    try:
        sh = (shell or "cmd").lower()

        # Prefer pwsh if available, otherwise fall back to Windows PowerShell
        if sh in ("powershell", "pwsh"):
            pwsh_exec = shutil.which("pwsh") or shutil.which("powershell")
            if not pwsh_exec:
                return "PowerShell executable not found on PATH"
            args = [pwsh_exec, "-NoProfile", "-NonInteractive", "-Command", cmd]
            completed = subprocess.run(args, capture_output=True, text=True)

        elif sh == "cmd":
            # Use explicit cmd /c to run the command and keep piping semantics
            args = ["cmd", "/c", cmd]
            completed = subprocess.run(args, capture_output=True, text=True)

        else:
            # For other shells (e.g., bash on WSL), fall back to shell=True
            completed = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        return completed.stdout if completed.returncode == 0 else completed.stderr
    except Exception as e:
        return str(e)


def extract_json(text) -> Optional[dict]:
    """Robustly extract the first valid JSON object from free text.

    Strategies used (in order):
    - Try parsing the whole text as JSON.
    - Extract JSON from fenced code blocks (```json ... ``` and ``` ... ```).
    - Extract balanced {...} substrings and attempt to parse them, applying
      light, safe fixes (remove trailing commas, escape backslashes) only when
      necessary.
    Returns a parsed object or None.
    """
    def _candidates_from_fences(t: str) -> List[str]:
        found: List[str] = []
        for m in re.finditer(r"```(?:json)?\n(.*?)```", t, re.DOTALL | re.IGNORECASE):
            found.append(m.group(1).strip())
        return found

    def _balanced_brace_candidates(t: str) -> List[str]:
        candidates: List[str] = []
        text = t
        for i, ch in enumerate(text):
            if ch == '{':
                stack = 1
                j = i + 1
                while j < len(text) and stack > 0:
                    if text[j] == '{':
                        stack += 1
                    elif text[j] == '}':
                        stack -= 1
                    j += 1
                if stack == 0:
                    candidates.append(text[i:j])
        return candidates

    def _try_parse(s: str) -> Optional[object]:
        s = s.strip()
        # Unescape common HTML entities and trim
        s = html.unescape(s)
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            # Try light fixes: remove trailing commas, escape backslashes, convert single quotes to double when likely
            s_fixed = re.sub(r",\s*}\s*$", "}", s)
            s_fixed = re.sub(r",\s*\]\s*$", "]", s_fixed)
            s_fixed = s_fixed.replace('\\', '\\\\')
            if s_fixed.count("'") > s_fixed.count('"'):
                s_fixed = s_fixed.replace("'", '"')
            try:
                return json.loads(s_fixed)
            except json.JSONDecodeError:
                return None

    # 1) Try entire text and ensure it's a dict
    try:
        parsed_whole = json.loads(text)
        if isinstance(parsed_whole, dict):
            return parsed_whole
    except json.JSONDecodeError:
        pass

    # 2) Code fences
    candidates = _candidates_from_fences(text)

    # 3) Balanced-brace candidates
    if not candidates:
        candidates = _balanced_brace_candidates(text)

    for cand in candidates:
        parsed = _try_parse(cand)
        if isinstance(parsed, dict):
            return parsed

    return None


def _strip_markdown(text: str) -> str:
    """Remove common markdown decorations to get plain text for summaries."""
    # Remove code fences first
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    # Remove inline code
    text = re.sub(r"`([^`]*)`", r"\1", text)
    # Remove bold/italic markers
    text = re.sub(r"\*\*|__|\*|_", "", text)
    # Remove headings and blockquotes
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^>\s*", "", text, flags=re.MULTILINE)
    # Remove links but keep text
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_summary(text: str, max_words: int = 50) -> str:
    """Heuristic summary extraction.

    Looks for a '**Summary**' or 'Summary:' block. If none, falls back to the
    first max_words of meaningful plain text (markdown stripped).
    """
    if not text:
        return ""

    # Try to capture **Summary** blocks
    m = re.search(r"(?is)\*\*Summary\*\*\s*[:\-]?\s*(.+?)(?:\n\n|$)", text)
    if not m:
        m = re.search(r"(?is)^Summary\s*[:\-]?\s*(.+?)(?:\n\n|$)", text)

    if m:
        summary_raw = m.group(1).strip()
        summary = _strip_markdown(summary_raw)
    else:
        # Fallback to the first paragraph of plain text
        plain = _strip_markdown(text)
        # Remove leading 'Outputs:' blocks or other noise
        plain = re.sub(r"(?i)outputs?:\s*", "", plain)
        summary = plain

    # Truncate to max_words
    words = summary.split()
    if len(words) > max_words:
        summary = " ".join(words[:max_words]) + " …"

    return summary

def main():
    os_type = platform.system()
    print(f"🤖 Detected OS: {os_type}")
    print("Type your natural language requests. Type 'exit' to quit.\n")

    while True:
        user_input = input("📝 Enter your request (or 'exit' to quit): ")
        if user_input.lower() == "exit":
            break

        system_prompt = f"""
You are a helpful assistant. 
"shell": "cmd" for Windows cmd, "powershell" for Windows PowerShell, "bash" for Linux/Mac.
The user is running on **{os_type}** system.
Convert the following request into valid terminal commands for this OS.
Always give only the output JSON in the following format :

{{
  "commands": [
    {{"shell": "cmd", "cmd": "example command"}},
    {{"shell": "cmd", "cmd": "example command"}}
  ]
}}

Strictly follow this format and do not include any other text.

User request: {user_input}
"""

        llm_response = query_llm(system_prompt)
        print(f"\n🤖 LLM raw response:\n{llm_response}\n")

        parsed = extract_json(llm_response)
        if not parsed:
            print("⚠️ Attempting JSON correction...")
            retry_prompt = f"Extract ONLY the valid JSON from this response:\n{llm_response}"
            fixed_json = query_llm(retry_prompt)
            parsed = extract_json(fixed_json)

        if not parsed:
            print("❌ Failed to parse JSON.")
            continue

        commands = parsed.get("commands", [])
        print(f"✅ Parsed {len(commands)} commands.")

        all_output = f"System: {os_type}\n"
        for i, c in enumerate(commands, start=1):
            shell = c.get("shell", "cmd")
            cmd = c.get("cmd", "")
            print(f"▶️ Running {i}/{len(commands)} in {shell}: {cmd}")
            output = run_command(shell, cmd)
            all_output += f"\n--- Command {i} ({cmd}) Output ---\n{output}\n"
            print(output)

        while True:
            print("🔄 Sending outputs back for feedback...")
            feedback_prompt = f"""
The following commands were executed for the user's request: {user_input}

Outputs:
{all_output}

Please provide:
1. A 50-word summary of the results.
2. If any failed, suggest corrected commands ONLY in this format:
{{
  "commands": [
    {{"shell": "cmd", "cmd": "corrected command"}}
  ]
}}
"""
            feedback = query_llm(feedback_prompt)
            print(f"\n📊 LLM Feedback:\n{feedback}\n")

            # Try parsing the JSON summary from feedback
            feedback_json = extract_json(feedback)

            # If JSON has a summary, use it. Otherwise, fall back to heuristic extraction.
            if feedback_json and isinstance(feedback_json.get("summary", None), str):
                print(f"📝 Summary:\n➡️ {feedback_json['summary']}\n")
            else:
                summary = extract_summary(feedback, max_words=50)
                if summary:
                    print(f"📝 Summary (heuristic):\n➡️ {summary}\n")
                else:
                    print("⚠️ Failed to extract summary from feedback.\n")

            corrected = extract_json(feedback)

            # Treat missing or empty 'commands' as no corrections
            if not corrected or not isinstance(corrected, dict):
                print("✅ No corrections suggested.\n Task Done Successfully.\n")
                break

            corrected_commands = corrected.get("commands")
            if not isinstance(corrected_commands, list) or len(corrected_commands) == 0:
                print("✅ No corrections suggested.\n Task Done Successfully.\n")
                break

            confirm = input("⚠️ Apply corrected commands? (yes/no): ").strip().lower()
            if confirm != "yes":
                break

            commands = corrected_commands
            print(f"▶️ Running {len(commands)} corrected commands...\n")
            all_output = ""
            for i, c in enumerate(commands, start=1):
                shell = c.get("shell", "cmd")
                cmd = c.get("cmd", "")
                print(f"▶️ Running corrected {i}/{len(commands)} in {shell}: {cmd}")
                output = run_command(shell, cmd)
                all_output += f"\n--- Corrected Command {i} ({cmd}) Output ---\n{output}\n"
                print(output)

if __name__ == "__main__":
    main()
