# System\_assistant

A powerful assistant tool that transforms your natural language requests into system commands using the Groq API and executes them intelligently. This project leverages the llama-3.1-8b-instant model to interpret your intents, execute commands, handle errors, and provide clear summaries.

## 🔍 Features

* Natural language to system command conversion.
* Intelligent execution of commands with error handling.
* Provides a concise summary of results.
* Supports cmd, PowerShell, and bash across Windows, Linux, and Mac.
* Two modes of operation: CLI mode and GUI mode.

## 🚀 Setup Instructions

1. Install dependencies and if needed add virtual environment too:

   ```bash
   pip install -r requirements.txt
   ```

2. Obtain your free Groq API key:

   * Visit [https://www.groq.ai/](https://www.groq.ai/).
   * Sign up or log in.
   * Go to [https://console.groq.com/keys](https://console.groq.com/keys) and copy your API key.

3. Create a `.env` file in the project root:

   ```env
   GROQ_API_KEY=your_groq_api_key_here
   ```

4. Run the agent in your preferred mode:

   ### CLI Mode

   ```bash
   python terminal_agent.py
   ```

   ### GUI Mode

   ```bash
   python gui.py
   ```

## ⚡ Usage

Simply type your natural language request when prompted, for example:

```text
find the IP address of this device
```

The system will:

* Convert your request into executable system commands.
* Execute them intelligently.
* Provide a clear and concise summary of the results.

## 🎯 Supported Commands

* Detect network configuration (e.g., IP addresses).
* System information retrieval.
* File system operations.
* Package management (OS dependent).
* And more, via custom user prompts.

## 🌐 Supported Platforms

* Windows (cmd, PowerShell)
* Linux (bash)
* macOS (bash)

## 🧱 Technology Stack

* Python 3
* Groq API (llama-3.1-8b-instant model)

## 📚 References

* Groq API Documentation: [https://www.groq.ai/docs](https://www.groq.ai/docs)

---

Contributions and feedback are welcome. This project is ideal for developers, sysadmins, and power users who want to simplify system management tasks using natural language.
