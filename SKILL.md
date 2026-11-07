---
name: ghost-cua
description: Run zero-interruption background analysis, multimodal file submission, and deep social research through native macOS desktop apps (Gemini and Meta AI).
---

# GhostCUA Skill: Background Desktop Automation

Operates native macOS desktop applications (**Google Gemini** and **Meta AI**) completely in the background with **zero user interruption**:
- **0 Cursor Movement** (physical mouse pointer stays untouched)
- **0 Focus Theft** (active frontmost app never yields keyboard or window focus)
- **0 Desktop/Space Switching** (direct process-targeted AppleEvents to PID, never LaunchServices)
- **0 Window Manipulation** (never resizes, activates, or minimizes windows)
- **0 Screen Recording Permissions** (pure Accessibility tree traversal)

---

## 1. Google Gemini Desktop (`com.google.GeminiMacOS`)

### Multimodal Query (Video, Image, PDF, Audio, Doc)
```bash
python gemini_background.py \
  --file "/path/to/media.mp4" \
  --prompt "Summarize what happens in this video in 2 sentences." \
  --out "output.txt" \
  --json
```

### Text-Only Query (No File)
```bash
python gemini_background.py \
  --prompt "Explain zero-copy serialization in 1 sentence." \
  --json
```

**Flags:**
- `--file, -f, --video, -v`: (Optional) Local file to attach.
- `--prompt, -p`: (Required) Prompt or analysis instructions.
- `--out, -o`: (Optional) Output text file path.
- `--new-chat`: (Optional) Start in a fresh chat session.
- `--json`: (Optional) Outputs structured JSON envelope `{ok: true, file: "...", response: "..."}`.

---

## 2. Meta AI Desktop (`com.meta.endo.vanilla`)

### Deep Research in Thinking Mode (Instagram Trends & Audience Sentiment)
```bash
python meta_ai_background.py \
  --prompt "What are the top 3 trending reel formats on Instagram right now?" \
  --out "instagram_trends.txt" \
  --new-chat \
  --json
```

**Flags:**
- `--prompt, -p`: (Required) Research prompt or query.
- `--out, -o`: (Optional) Output text file path.
- `--new-chat`: (Optional) Click 'New chat' to start in a fresh session.
- `--no-thinking`: (Optional) Disable automatic Thinking mode verification.
- `--timeout, -t`: (Optional) Max generation timeout in seconds (default: 360).
- `--json`: (Optional) Outputs structured JSON envelope.

---

## 3. MCP Server Configuration (For Coding Agents)

Add to `.cursor/mcp.json`, `~/.gemini/antigravity/mcp_config.json`, or `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ghost-cua-gemini": {
      "command": "python",
      "args": ["/path/to/ghost-cua/gemini_mcp.py"]
    },
    "ghost-cua-meta-ai": {
      "command": "python",
      "args": ["/path/to/ghost-cua/meta_ai_mcp.py"]
    }
  }
}
```

### Available Tools:
- `gemini_query`: Multimodal video/image/doc analysis & general reasoning.
- `meta_ai_research`: Deep Instagram research, trending reel hooks, and audience sentiment in Thinking mode.

---

## 4. Building Adapters for Other macOS Apps
See [`AGENT.md`](AGENT.md) for the universal 5-phase blueprint to automate any native macOS application (ChatGPT, Claude desktop, etc.) zero-shot.
