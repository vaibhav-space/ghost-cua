# AGENT.md: Universal Background Desktop Automation Blueprint

> **For AI Coding Agents (Cursor, Claude Code, Antigravity, Windsurf, Codex)**:
> This specification defines how to implement zero-interruption background automation for **ANY native macOS desktop application** (Meta AI, ChatGPT, Claude, Slack, Mail, etc.) without stealing mouse focus, keyboard focus, or switching macOS Spaces.

---

## 1. Core Directives & Invariants

When building background automation for a new macOS application, you MUST enforce these non-negotiable rules:
1. **Never steal focus**: Never call `NSApp.activate(ignoringOtherApps: true)` or simulated global clicks on the active desktop.
2. **Never simulate physical keystrokes**: Always write directly to `AXUIElementSetAttributeValue(ref, "AXValue", text)`.
3. **Never use `/usr/bin/open`**: Always use direct Carbon AppleEvents (`aevt/odoc`) with `kAENeverInteract` (`0x00000010`) targeted to the process PID.
4. **Never wait without verifying submission**: Media files buffer asynchronously. Always loop until composer text clears or generation starts before entering the waiting phase.
5. **Always preserve user clipboard**: If reading responses via a native copy button, back up user pasteboard types and data first, and restore them immediately after reading.

---

## 2. 5-Step Implementation Recipe for Any Target App

### Step 1: Discover Target Process & Bundle ID
Run this inspection probe to find the running application and its main window:

```python
import Cocoa
from ApplicationServices import AXUIElementCreateApplication, AXUIElementCopyAttributeValue

ws = Cocoa.NSWorkspace.sharedWorkspace()
for app in ws.runningApplications():
    bundle_id = app.bundleIdentifier()
    # E.g. com.facebook.MetaAI, com.openai.chat, com.anthropic.claudedesktop
    if bundle_id and any(k in bundle_id.lower() for k in ["meta", "chatgpt", "claude"]):
        print(f"Found: {bundle_id} (PID: {app.processIdentifier()})")
```

### Step 2: Map the Accessibility Tree (DFS Traversal)
Inspect the app's accessibility tree to identify selectors for:
1. Composer Text Area (`AXTextArea` or `AXTextField`)
2. File Attachment Button (if applicable)
3. Submit / Send Button (`AXButton` with `send_button` or `Submit`)
4. Copy Response Button (or response bubbles)

```python
def walk_tree_dfs(root_el, max_depth=35, max_nodes=5000):
    results = []
    stack = [(root_el, 0)]
    while stack and len(results) < max_nodes:
        el, depth = stack.pop()
        if depth > max_depth:
            continue
        _, role = AXUIElementCopyAttributeValue(el, "AXRole", None)
        _, desc = AXUIElementCopyAttributeValue(el, "AXDescription", None)
        _, val = AXUIElementCopyAttributeValue(el, "AXValue", None)
        _, ax_id = AXUIElementCopyAttributeValue(el, "AXIdentifier", None)
        results.append({"ref": el, "role": role, "desc": desc, "val": val, "id": ax_id})
        
        err, children = AXUIElementCopyAttributeValue(el, "AXChildren", None)
        if err == 0 and children:
            for c in reversed(children):
                stack.append((c, depth + 1))
    return results
```

### Step 3: Implement Direct Process Document Attachment
Deliver files directly to the target application PID without going through LaunchServices:

```python
import struct, os
import Cocoa
from Foundation import NSURL

def attach_file_to_pid(pid: int, file_path: str):
    abs_path = os.path.abspath(file_path)
    target = Cocoa.NSAppleEventDescriptor.descriptorWithProcessIdentifier_(pid)
    event = Cocoa.NSAppleEventDescriptor.appleEventWithEventClass_eventID_targetDescriptor_returnID_transactionID_(
        struct.unpack(">I", b"aevt")[0],
        struct.unpack(">I", b"odoc")[0],
        target, 0, 0
    )
    file_list = Cocoa.NSAppleEventDescriptor.listDescriptor()
    file_url = NSURL.fileURLWithPath_(abs_path)
    file_desc = Cocoa.NSAppleEventDescriptor.descriptorWithDescriptorType_data_(
        struct.unpack(">I", b"furl")[0],
        file_url.absoluteString().encode("utf-8")
    )
    file_list.insertDescriptor_atIndex_(file_desc, 1)
    event.setDescriptor_forKeyword_(file_list, struct.unpack(">I", b"----")[0])
    
    # 0x00000011 = kAENoReply | kAENeverInteract (prevents layer switching)
    event.sendEventWithOptions_timeout_error_(0x00000011, 5, None)
```

### Step 4: Implement Invariant-Checked Prompt & Submit
```python
def submit_prompt(ax_app, prompt_text: str):
    main_win = get_main_window(ax_app)
    nodes = walk_tree_dfs(main_win)
    
    # 1. Inject prompt
    text_areas = [n for n in nodes if n["role"] in ("AXTextArea", "AXTextField")]
    AXUIElementSetAttributeValue(text_areas[0]["ref"], "AXValue", prompt_text)
    
    # 2. Verified submission loop
    for _ in range(15):
        nodes = walk_tree_dfs(main_win)
        submit_btn = [n for n in nodes if n["role"] == "AXButton" and n["desc"] in ("Submit", "Send")]
        if submit_btn:
            AXUIElementPerformAction(submit_btn[0]["ref"], "AXPress")
            time.sleep(1.0)
            
            # Check if text cleared or stop button appeared
            nodes_after = walk_tree_dfs(main_win)
            ta = [n for n in nodes_after if n["role"] in ("AXTextArea", "AXTextField")]
            if ta and not str(ta[0]["val"] or "").strip():
                return  # Confirmed submission!
        time.sleep(0.5)
```

### Step 5: Implement Response Extraction & Clipboard Restoration
```python
def extract_latest_response(ax_app) -> str:
    pb = Cocoa.NSPasteboard.generalPasteboard()
    
    # Backup user clipboard
    old_types = pb.types()
    old_data = {t: pb.dataForType_(t) for t in old_types} if old_types else {}
    
    try:
        # Find copy button and trigger AXPress
        main_win = get_main_window(ax_app)
        nodes = walk_tree_dfs(main_win)
        copy_btns = [n for n in nodes if n["role"] == "AXButton" and "copy" in str(n["desc"]).lower()]
        AXUIElementPerformAction(copy_btns[-1]["ref"], "AXPress")
        time.sleep(0.4)
        response_text = pb.stringForType_(Cocoa.NSPasteboardTypeString)
        return response_text
    finally:
        # Restore user clipboard
        pb.clearContents()
        for t, data in old_data.items():
            pb.setData_forType_(data, t)
```

---

## 3. Reference Implementation
See [`gemini_background.py`](gemini_background.py) for the complete production reference implementation covering health checks, DFS tree traversal, verified submission retries, and JSON envelope serialization.
