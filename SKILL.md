---
name: gemini-desktop-automation
description: Run zero-interruption background analysis, multimodal file submission (video, image, pdf, doc), and text queries through the native macOS Gemini desktop application.
---

# Gemini Desktop Background Automation Skill

Operates the **native macOS Gemini desktop app (`com.google.GeminiMacOS`) completely in the background** with **zero user interruption**:
- **0 Cursor Movement** (real physical mouse pointer stays untouched)
- **0 Focus Theft** (active frontmost app never yields keyboard or window focus)
- **0 Desktop/Space Switching** (direct process-targeted AppleEvents to PID, never LaunchServices)
- **0 Window Manipulation** (never resizes, activates, or minimizes windows)
- **Universal Media Support**: Supports videos (`.mp4`, `.mov`), images (`.png`, `.jpg`, `.webp`), PDFs, audio, documents, and text-only queries.

---

## Quickstart

### 1. Query with a Video or File
```bash
python gemini_background.py \
  --file "/path/to/media.mp4" \
  --prompt "Summarize what happens in this video in 2 sentences." \
  --out "output.txt" \
  --json
```

### 2. Query with Text Only (No File)
```bash
python gemini_background.py \
  --prompt "What are the primary differences between Apple Silicon M4 and M5 architectures?" \
  --json
```

### Flags
- `--file, -f` (or `--video, -v`): (Optional) Local file to attach (video, image, pdf, audio, doc).
- `--prompt, -p`: (Required) Prompt or analysis instructions.
- `--out, -o`: (Optional) Output text file to write the extracted response.
- `--new-chat`: (Optional) Clicks 'New chat' button before submitting.
- `--json`: (Optional) Outputs structured JSON envelope `{ok: true, file: "...", response: "..."}`.

---

## MCP Server Configuration

To expose this capability to MCP-based coding agents (Antigravity, Claude Code, Cursor, Zed, Codex):

Add to `.mcp.json` or `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ghost-cua": {
      "command": "python",
      "args": ["/path/to/ghost-cua/gemini_mcp.py"]
    }
  }
}
```

### Available Tool
- `gemini_query`:
  - `prompt` (string, required): Instructions or question for Gemini.
  - `file_path` (string, optional): Local file to attach.
  - `output_path` (string, optional): File path to save response.
  - `new_chat` (boolean, optional): Whether to start a new chat.

---

## Technical Details: How Zero Interruption is Guaranteed

1. **Direct Process-Targeted AppleEvents**: Dispatches files straight to Gemini's PID (`kpid`) with `kAENeverInteract` (`0x00000011`), bypassing macOS LaunchServices `/usr/bin/open` and instructing AppleEvent Manager never to switch window layers.
2. **Native AX Text Injection**: Sets prompt text via `AXUIElementSetAttributeValue` on `AXTextArea`. Requires no simulated typing or window focus.
3. **Native AX Button Press**: Triggers `AXUIElementPerformAction(..., 'AXPress')` on `send_button` and `Copy response`. No mouse cursor events are generated.
4. **Clipboard Preservation**: Before reading Gemini's copied response, the user's current pasteboard types and data are backed up, and immediately restored after reading.

---

## macOS Configuration for Multi-Space Workflows

If Gemini is kept on a separate Space/Desktop, configure the following to ensure macOS never redirects your screen:

1. **Windowed Mode (Do Not Use macOS Native Full Screen)**:
   - Ensure Gemini is running as a standard window (not full-screen via the green button). Dedicated Full Screen spaces force macOS to switch views upon file receipt.
2. **Disable Automatic Space Switching**:
   - In **System Settings → Desktop & Dock → Mission Control**, turn OFF:
     *"When switching to an application, switch to a Space with open windows for the application"*.
   - Or run: `defaults write com.apple.dock workspaces-auto-swoosh -bool false && killall Dock`
   - *Side effects*: Zero. Gestures, Mission Control (F3), and trackpad swipes remain 100% intact.
3. **Assign to All Desktops (Optional)**:
   - Right-click Gemini icon in Dock → **Options** → **Assign To: All Desktops**.
