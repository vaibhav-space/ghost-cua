# GhostCUA 👻
### Zero-Interruption Background macOS Desktop Automation Engine

> **Operate Gemini, Meta AI, and native macOS desktop apps completely in the background — without stealing your mouse, losing keyboard focus, or switching desktops.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: macOS](https://img.shields.io/badge/Platform-macOS-black.svg?logo=apple&logoColor=white)](https://apple.com)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python&logoColor=white)](https://python.org)
[![Protocol: MCP](https://img.shields.io/badge/Protocol-MCP-8B5CF6.svg)](https://modelcontextprotocol.io)
[![Live Demo](https://img.shields.io/badge/Website-Live%20Demo-2563eb.svg)](https://vaibhav-space.github.io/ghost-cua/)

🌐 **[Explore the Interactive Landing Page & Live Simulator →](https://vaibhav-space.github.io/ghost-cua/)**

---

## The Problem with Modern "Computer Use Agents"

Existing desktop automation and CUA (Computer Use Agent) frameworks suffer from a fatal usability flaw: **they hijack your computer**.

- They move your physical mouse cursor while you are trying to work.
- They flash windows to the foreground, stealing keyboard focus mid-keystroke.
- They trigger macOS Mission Control Space-switching ("swooshing"), abruptly pulling your screen across virtual desktops.
- They rely on heavy screenshot loops that trip macOS Screen Recording permission errors (`SCK circuit breaker`).

**If an agent makes your computer unusable while it runs, it isn't an assistant — it's an interruption.**

---

## The Solution: GhostCUA

**GhostCUA** is a lightweight, pure-Python background automation engine and [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server for macOS. It allows AI agents and automation scripts to interact with native desktop applications with **zero computer interruption**:

| Metric | Traditional CUAs | **GhostCUA** |
| :--- | :--- | :--- |
| **Physical Mouse Movement** | Constantly moves/clicks | **0 cursor movement** |
| **Keyboard Focus** | Stolen mid-typing | **0 focus theft** (foreground app remains 100% active) |
| **Mission Control Spaces** | Abruptly switches desktops | **0 Space changes** |
| **Screen Recording Permissions** | Required (heavy screenshots) | **NOT required** (direct Accessibility tree inspection) |
| **Footprint & Bloat** | 150 MB – 1.1 GB multi-process engines | **~500 lines of pure Python + PyObjC** |
| **Clipboard Safety** | Overwrites pasteboard | **Full backup & instant restoration** |

---

## How It Works: The 5-Phase Zero-Interruption Pipeline

GhostCUA bypasses macOS WindowServer layer-switching through deep OS-level primitives:

```
[Target Discovery] ──> [Process-Targeted AppleEvent] ──> [AX Text Injection] ──> [Verified Submit Loop] ──> [Lossless Extraction]
  (PID Resolution)       (aevt/odoc + kAENeverInteract)      (Direct AXValue)        (Zero-Hang Media Buffer)    (Clipboard Preserved)
```

1. **Process-Targeted Document Dispatch**:
   Instead of using `/usr/bin/open` (which routes through LaunchServices and forces Mission Control to switch Spaces), GhostCUA constructs raw Carbon `aevt/odoc` AppleEvents delivered directly to the target application PID with the `kAENeverInteract` (`0x00000010`) flag. The target handles the file without switching window layers.
2. **Direct Accessibility Value Injection**:
   Sets prompt text directly on the application's `AXTextArea` via `AXUIElementSetAttributeValue`. Zero simulated keystrokes, zero key-window requirements.
3. **Background Process Actions**:
   Triggers UI actions (`send_button`, `Copy response`, mode selectors) via `AXUIElementPerformAction(..., "AXPress")` without generating hardware mouse events.
4. **Verified Submission Loop (Eliminates Media Buffering Hangs)**:
   When attaching large media (videos, images, PDFs), desktop apps take several seconds to buffer and index the file. GhostCUA actively verifies composer clearance before waiting, retrying submission until confirmed.
5. **Lossless Response Extraction**:
   Extracts responses via the native `Copy response` action while backing up and immediately restoring the user's pre-existing clipboard data.

---

## Supported Applications (Shipped Out-of-the-Box)

1. **Google Gemini Desktop (`com.google.GeminiMacOS`)**: 
   - Script: `gemini_background.py` | MCP: `gemini_mcp.py`
   - Multimodal video analysis, images, PDFs, audio, documents, and text queries.
2. **Meta AI Desktop (`com.meta.endo.vanilla`)**:
   - Script: `meta_ai_background.py` | MCP: `meta_ai_mcp.py`
   - Deep research on Instagram trends, audience sentiment, and creator analytics using Meta AI's native **Thinking mode**. Zero Instagram ban risk.
3. **ChatGPT / Claude / Any Native App**:
   - Follow the zero-shot recipe in [`AGENT.md`](AGENT.md) to build background automation for any macOS application in minutes.

---

## Quickstart

### 1. Prerequisites
- macOS (Apple Silicon or Intel)
- Python 3.10+
- Accessibility permissions enabled for Terminal / your IDE

### 2. Installation
```bash
git clone https://github.com/vaibhav-space/ghost-cua.git
cd ghost-cua

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Usage Examples

**Research Instagram trends via Meta AI (Thinking mode):**
```bash
python meta_ai_background.py \
  --prompt "What are the top 3 trending reel formats on Instagram right now?" \
  --out "instagram_trends.txt" \
  --new-chat \
  --json
```

**Analyze a video in the background via Gemini:**
```bash
python gemini_background.py \
  --file "/path/to/video.mp4" \
  --prompt "Summarize what happens in this video in 2 sentences." \
  --out "output.txt" \
  --json
```

**Text-only query via Gemini:**
```bash
python gemini_background.py \
  --prompt "Explain zero-copy serialization in 1 sentence." \
  --json
```

---

## MCP Server Integration (For Coding Agents)

To connect GhostCUA to **Claude Code, Cursor, Zed, Codex, or Antigravity**, add this to your MCP configuration (`~/.gemini/antigravity/mcp_config.json`, `.cursor/mcp.json`, or `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "ghost-cua-gemini": {
      "command": "/path/to/ghost-cua/.venv/bin/python",
      "args": ["/path/to/ghost-cua/gemini_mcp.py"]
    },
    "ghost-cua-meta-ai": {
      "command": "/path/to/ghost-cua/.venv/bin/python",
      "args": ["/path/to/ghost-cua/meta_ai_mcp.py"]
    }
  }
}
```

### Available Tools
- `gemini_query`: Multimodal video/image/doc analysis & general reasoning.
- `meta_ai_research`: Deep Instagram research, trending reel hooks, and audience sentiment in Thinking mode.

---

## macOS Configuration Best Practices

To guarantee that macOS never redirects your screen:
1. **Windowed Mode**: Run the target application as a standard window (not macOS native Full Screen via the green button). Dedicated Full Screen spaces force macOS to switch views upon file receipt.
2. **Leave Behind Active Windows or Hide (`Cmd+H`)**: Do not minimize to the Dock (`Cmd+M`), as macOS Cocoa deminiaturizes dock items upon file receipt. Leaving the window behind your browser or pressing `Cmd+H` operates 100% silently.
3. **Disable Automatic Space Swoosh (Optional)**:
   In **System Settings → Desktop & Dock → Mission Control**, turn OFF:
   *"When switching to an application, switch to a Space with open windows for the application"*.
   Or run in Terminal:
   ```bash
   defaults write com.apple.dock workspaces-auto-swoosh -bool false && killall Dock
   ```

---

## Extending to Other Applications

Want to build background automation for **Meta AI**, **ChatGPT**, or another desktop app?

Read **[`AGENT.md`](AGENT.md)** for the complete blueprint. Any AI coding agent can read `AGENT.md` and implement a dedicated background automation script for your application zero-shot.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
