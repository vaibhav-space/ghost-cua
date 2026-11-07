#!/usr/bin/env python3
"""
gemini_background.py - Universal Zero-Interruption Background Gemini Desktop Automation

Operates macOS Gemini.app completely in the background:
- 0 Cursor Movement (physical mouse cursor untouched)
- 0 Focus Theft (active frontmost application untouched)
- 0 Desktop / Space Switching (uses direct process-targeted AppleEvents to PID, never LaunchServices)
- 0 Window Activation (direct Accessibility mutations)
- Supports any file type: Videos (.mp4, .mov), Images (.png, .jpg, .webp), PDFs, Documents, Audio
- Supports text-only prompts (file attachment optional)
- Preserves user clipboard
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import struct
import subprocess
import sys
import time
from typing import Any, Optional

import ApplicationServices
from ApplicationServices import (
    AXUIElementCopyAttributeNames,
    AXUIElementCopyAttributeValue,
    AXUIElementCreateApplication,
    AXUIElementPerformAction,
    AXUIElementSetAttributeValue,
    kAXErrorSuccess,
)
from AppKit import NSPasteboard, NSStringPboardType, NSWorkspace
from Foundation import NSAppleEventDescriptor, NSURL
from Quartz import CGEventCreate, CGEventGetLocation

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("gemini_background")

APP_BUNDLE_ID = "com.google.GeminiMacOS"
APP_PATH = "/Applications/Gemini.app"


class BackgroundAutomationError(Exception):
    """Raised when a background automation step fails."""


def get_frontmost_bundle_id() -> Optional[str]:
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return app.bundleIdentifier() if app else None


def get_cursor_position() -> tuple[float, float]:
    event = CGEventCreate(None)
    if event:
        loc = CGEventGetLocation(event)
        return (loc.x, loc.y)
    return (0.0, 0.0)


def get_gemini_pid() -> Optional[int]:
    try:
        output = subprocess.check_output(["pgrep", "-x", "Gemini"]).decode().strip()
        pids = [int(p) for p in output.split() if p.isdigit()]
        return pids[0] if pids else None
    except subprocess.CalledProcessError:
        return None


def ensure_gemini_running(timeout: float = 15.0) -> int:
    pid = get_gemini_pid()
    if pid is not None:
        return pid

    logger.info("Gemini is not running. Launching safely in background...")
    subprocess.run(["open", "-g", "-a", APP_PATH], check=True)

    start = time.time()
    while time.time() - start < timeout:
        pid = get_gemini_pid()
        if pid is not None:
            time.sleep(1.0)
            return pid
        time.sleep(0.5)

    raise BackgroundAutomationError(f"Failed to launch {APP_PATH} within {timeout}s.")


def get_gemini_main_window(ax_app: Any, timeout: float = 10.0) -> Any:
    start = time.time()
    while time.time() - start < timeout:
        for attr in ("AXMainWindow", "AXFocusedWindow"):
            err, win = AXUIElementCopyAttributeValue(ax_app, attr, None)
            if err == kAXErrorSuccess and win is not None:
                _, is_fs = AXUIElementCopyAttributeValue(win, "AXFullScreen", None)
                if is_fs:
                    logger.warning(
                        "Gemini is currently in macOS native Full Screen mode. "
                        "macOS dedicated Full Screen spaces cause desktop redirection on file open. "
                        "For zero-interruption background operation, exit Full Screen mode on Gemini."
                    )
                return win

        err, wins = AXUIElementCopyAttributeValue(ax_app, "AXWindows", None)
        if err == kAXErrorSuccess and wins and len(wins) > 0:
            win = wins[0]
            _, is_fs = AXUIElementCopyAttributeValue(win, "AXFullScreen", None)
            if is_fs:
                logger.warning(
                    "Gemini is currently in macOS native Full Screen mode. "
                    "macOS dedicated Full Screen spaces cause desktop redirection on file open. "
                    "For zero-interruption background operation, exit Full Screen mode on Gemini."
                )
            return win

        time.sleep(0.5)

    raise BackgroundAutomationError("Could not resolve Gemini main window via Accessibility.")


class Node:
    __slots__ = ("ref", "role", "subrole", "desc", "help", "val", "label", "ax_id")

    def __init__(
        self,
        ref: Any,
        role: Optional[str] = None,
        subrole: Optional[str] = None,
        desc: Optional[str] = None,
        help_text: Optional[str] = None,
        val: Optional[str] = None,
        label: Optional[str] = None,
        ax_id: Optional[str] = None,
    ):
        self.ref = ref
        self.role = role
        self.subrole = subrole
        self.desc = desc
        self.help = help_text
        self.val = val
        self.label = label
        self.ax_id = ax_id

    def __repr__(self) -> str:
        return (
            f"Node(role={self.role!r}, id={self.ax_id!r}, desc={self.desc!r}, "
            f"help={self.help!r}, val={self.val!r})"
        )


def walk_tree_dfs(root_el: Any, max_depth: int = 35, max_nodes: int = 5000) -> list[Node]:
    """Depth-First Search traversal of accessibility tree."""
    results: list[Node] = []
    stack: list[tuple[Any, int]] = [(root_el, 0)]

    while stack and len(results) < max_nodes:
        el, depth = stack.pop()
        if depth > max_depth:
            continue

        _, role = AXUIElementCopyAttributeValue(el, "AXRole", None)
        _, subrole = AXUIElementCopyAttributeValue(el, "AXSubrole", None)
        _, desc = AXUIElementCopyAttributeValue(el, "AXDescription", None)
        _, help_text = AXUIElementCopyAttributeValue(el, "AXHelp", None)
        _, val = AXUIElementCopyAttributeValue(el, "AXValue", None)
        _, label = AXUIElementCopyAttributeValue(el, "AXTitle", None)
        _, ax_id = AXUIElementCopyAttributeValue(el, "AXIdentifier", None)

        val_str = str(val) if val is not None else None
        node = Node(el, role, subrole, desc, help_text, val_str, label, ax_id)
        results.append(node)

        err, children = AXUIElementCopyAttributeValue(el, "AXChildren", None)
        if err == kAXErrorSuccess and children:
            for child in reversed(children):
                stack.append((child, depth + 1))

    return results


def start_new_chat(ax_app: Any) -> None:
    """Click 'New chat' button to start with a fresh composer."""
    main_win = get_gemini_main_window(ax_app)
    nodes = walk_tree_dfs(main_win)
    new_chat_btns = [
        n
        for n in nodes
        if n.role == "AXButton"
        and (n.desc == "New chat" or n.label == "New chat" or "New chat" in str(n.help or ""))
    ]
    if new_chat_btns:
        logger.info("Resetting composer via background 'New chat' action...")
        AXUIElementPerformAction(new_chat_btns[0].ref, "AXPress")
        time.sleep(1.0)


def attach_file_background(
    file_path: str, ax_app: Any, pid: int, timeout: float = 20.0
) -> None:
    """
    Attach any file (video, image, pdf, document, audio) to Gemini in the background.
    Uses direct process-targeted AppleEvent (aevt/odoc) sent directly to Gemini's PID.
    NEVER uses LaunchServices or /usr/bin/open, preventing macOS WindowServer Space switches.
    """
    abs_path = os.path.abspath(file_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"File does not exist: {abs_path}")

    filename = os.path.basename(abs_path)
    logger.info(
        "Attaching file '%s' via direct process-targeted AppleEvent to PID %d...",
        filename,
        pid,
    )

    target = NSAppleEventDescriptor.descriptorWithProcessIdentifier_(pid)
    event = (
        NSAppleEventDescriptor.appleEventWithEventClass_eventID_targetDescriptor_returnID_transactionID_(
            struct.unpack(">I", b"aevt")[0],
            struct.unpack(">I", b"odoc")[0],
            target,
            0,
            0,
        )
    )
    file_list = NSAppleEventDescriptor.listDescriptor()
    file_url = NSURL.fileURLWithPath_(abs_path)
    file_desc = NSAppleEventDescriptor.descriptorWithDescriptorType_data_(
        struct.unpack(">I", b"furl")[0],
        file_url.absoluteString().encode("utf-8"),
    )
    file_list.insertDescriptor_atIndex_(file_desc, 1)
    event.setDescriptor_forKeyword_(file_list, struct.unpack(">I", b"----")[0])

    # Send with kAENoReply (0x00000001) | kAENeverInteract (0x00000010) = 0x00000011
    # kAENeverInteract informs the AppleEvent target never to switch layer or interact with user.
    res, err = event.sendEventWithOptions_timeout_error_(0x00000011, 5, None)
    if err:
        raise BackgroundAutomationError(f"Direct AppleEvent failed to deliver to Gemini PID {pid}: {err}")

    # Poll AX tree to verify attachment
    logger.info("Verifying file attachment in Gemini composer...")
    start = time.time()
    while time.time() - start < timeout:
        main_win = get_gemini_main_window(ax_app)
        nodes = walk_tree_dfs(main_win)
        for n in nodes:
            if (
                filename in str(n.help or "")
                or filename in str(n.label or "")
                or filename in str(n.desc or "")
            ):
                logger.info("File attachment verified in accessibility tree.")
                return
        time.sleep(0.4)

    raise BackgroundAutomationError(
        f"Timed out after {timeout}s waiting for '{filename}' to appear in Gemini composer."
    )


def ensure_chat_mode(main_win: Any) -> None:
    """Ensure Gemini is in 'Chat' mode rather than 'Task' mode if the toggle is present."""
    nodes = walk_tree_dfs(main_win, max_depth=12)
    for n in nodes:
        if n.role == "AXButton" and str(n.desc or "").strip().lower() == "chat":
            AXUIElementPerformAction(n.ref, "AXPress")
            time.sleep(0.3)
            return


def enter_prompt_background(prompt: str, ax_app: Any, timeout: float = 10.0) -> None:
    logger.info("Setting prompt text via native accessibility...")
    start = time.time()
    while time.time() - start < timeout:
        main_win = get_gemini_main_window(ax_app)
        ensure_chat_mode(main_win)
        nodes = walk_tree_dfs(main_win)
        text_areas = [n for n in nodes if n.role == "AXTextArea"]
        if text_areas:
            ta = text_areas[0]
            err = AXUIElementSetAttributeValue(ta.ref, "AXValue", prompt)
            if err == kAXErrorSuccess:
                logger.info("Prompt text injected successfully.")
                time.sleep(0.4)
                return
            else:
                logger.warning("AXUIElementSetAttributeValue error code %d", err)
        time.sleep(0.5)

    raise BackgroundAutomationError("Could not find or set prompt in Gemini AXTextArea.")


def count_copy_response_buttons(ax_app: Any) -> int:
    try:
        main_win = get_gemini_main_window(ax_app)
        nodes = walk_tree_dfs(main_win)
        return len([n for n in nodes if n.role == "AXButton" and n.desc == "Copy response"])
    except Exception:
        return 0


def submit_request_background(ax_app: Any, timeout: float = 15.0) -> None:
    """
    Submits the prompt in the background and verifies that submission actually succeeded
    by polling for the AXTextArea to clear or the Stop button to appear.
    """
    logger.info("Submitting request via background AXPress on Submit button...")
    start = time.time()
    
    while time.time() - start < timeout:
        main_win = get_gemini_main_window(ax_app)
        nodes = walk_tree_dfs(main_win)
        
        # Check if already submitted (Stop button present or text area empty)
        stop_btns = [n for n in nodes if n.role == "AXButton" and "stop" in str(n.desc or "").lower()]
        text_areas = [n for n in nodes if n.role == "AXTextArea"]
        
        if stop_btns:
            logger.info("Submission confirmed: Generation started (Stop button present).")
            return
            
        submit_btns = [
            n
            for n in nodes
            if n.role == "AXButton"
            and (n.ax_id == "send_button" or str(n.desc or "").strip().lower() in ("submit", "send") or "Send" in str(n.help or ""))
        ]
        
        if submit_btns:
            btn = submit_btns[0]
            AXUIElementPerformAction(btn.ref, "AXPress")
            logger.info("Triggered AXPress on Submit button. Verifying composer clearance...")
            time.sleep(1.0)
            
            # Re-check text area
            main_win = get_gemini_main_window(ax_app)
            nodes = walk_tree_dfs(main_win)
            text_areas = [n for n in nodes if n.role == "AXTextArea"]
            if text_areas and not str(text_areas[0].val or "").strip():
                logger.info("Submission confirmed: Composer text cleared.")
                return
                
        time.sleep(0.5)

    raise BackgroundAutomationError("Could not confirm submission within timeout.")


def wait_for_generation_complete(
    ax_app: Any, initial_copy_count: int, timeout: float = 180.0
) -> None:
    logger.info("Monitoring generation state in background...")
    start = time.time()

    while time.time() - start < timeout:
        main_win = get_gemini_main_window(ax_app)
        nodes = walk_tree_dfs(main_win)

        stop_btns = [
            n for n in nodes if n.role == "AXButton" and "Stop" in str(n.desc or n.label or "")
        ]
        copy_btns = [
            n for n in nodes if n.role == "AXButton" and n.desc == "Copy response"
        ]

        # Generation completes when a new Copy response button is present and Stop button is gone
        if len(copy_btns) > initial_copy_count and not stop_btns:
            logger.info(
                "Generation complete (new Copy response button detected, count: %d -> %d).",
                initial_copy_count,
                len(copy_btns),
            )
            time.sleep(0.5)
            return

        time.sleep(0.8)

    raise BackgroundAutomationError(f"Generation timed out after {timeout}s.")


def extract_response(ax_app: Any) -> str:
    """Extract complete response text using Copy response button with clipboard preservation."""
    logger.info("Extracting response via Copy response button...")
    pb = NSPasteboard.generalPasteboard()

    # 1. Backup user clipboard
    old_types = pb.types()
    old_data: dict[str, Any] = {}
    if old_types:
        for t in old_types:
            try:
                data = pb.dataForType_(t)
                if data:
                    old_data[t] = data
            except Exception:
                pass

    try:
        main_win = get_gemini_main_window(ax_app)
        nodes = walk_tree_dfs(main_win)
        copy_btns = [
            n for n in nodes if n.role == "AXButton" and n.desc == "Copy response"
        ]

        if not copy_btns:
            raise BackgroundAutomationError("No 'Copy response' button found in accessibility tree.")

        # Always take the last Copy response button (latest turn)
        last_copy_btn = copy_btns[-1]

        # Clear pasteboard before copy
        pb.clearContents()

        err = AXUIElementPerformAction(last_copy_btn.ref, "AXPress")
        if err != kAXErrorSuccess:
            raise BackgroundAutomationError(f"AXPress on 'Copy response' failed with code {err}.")

        # Read copied string with short polling
        response_text = ""
        for _ in range(25):
            time.sleep(0.1)
            copied = pb.stringForType_(NSStringPboardType)
            if copied and copied.strip():
                response_text = copied.strip()
                break

        if not response_text:
            raise BackgroundAutomationError("Clipboard was empty after pressing 'Copy response'.")

        return response_text

    finally:
        # 2. Restore user clipboard if backup was taken
        if old_data:
            pb.clearContents()
            for t, data in old_data.items():
                try:
                    pb.setData_forType_(data, t)
                except Exception:
                    pass


def run_gemini_workflow(
    prompt: str,
    file_path: Optional[str] = None,
    output_path: Optional[str] = None,
    new_chat: bool = False,
) -> str:
    """
    Execute complete end-to-end background Gemini automation workflow.
    `file_path` is optional: if omitted, executes a text-only prompt.
    """
    app_before = get_frontmost_bundle_id()
    cursor_before = get_cursor_position()
    logger.info(
        "Initial State | Frontmost: %s | Cursor: (%.1f, %.1f)",
        app_before,
        cursor_before[0],
        cursor_before[1],
    )

    t0 = time.time()

    # 1. Ensure Gemini is running in background
    pid = ensure_gemini_running()
    ax_app = AXUIElementCreateApplication(pid)

    # 2. Optional: reset composer to new chat
    if new_chat:
        start_new_chat(ax_app)

    # 3. Snapshot initial Copy response button count
    initial_copy_count = count_copy_response_buttons(ax_app)
    logger.info("Baseline turn count: %d previous response(s)", initial_copy_count)

    # 4. Attach file if provided (video, image, pdf, audio, etc.)
    if file_path:
        attach_file_background(file_path, ax_app, pid)
    else:
        logger.info("No file specified. Proceeding with text-only prompt.")

    # 5. Inject prompt
    enter_prompt_background(prompt, ax_app)

    # 6. Submit
    submit_request_background(ax_app)

    # 7. Wait for generation
    wait_for_generation_complete(ax_app, initial_copy_count)

    # 8. Extract response
    response_text = extract_response(ax_app)

    elapsed = time.time() - t0
    logger.info("Workflow completed in %.2fs. Response length: %d chars", elapsed, len(response_text))

    # Safety Check: Verify active application and cursor position after completion
    app_after = get_frontmost_bundle_id()
    cursor_after = get_cursor_position()
    logger.info(
        "Final State | Frontmost: %s | Cursor: (%.1f, %.1f)",
        app_after,
        cursor_after[0],
        cursor_after[1],
    )

    if app_before and app_after and app_before != app_after:
        logger.error(
            "CRITICAL: Frontmost application changed! (%s -> %s)", app_before, app_after
        )
    else:
        logger.info("VERIFIED: Zero focus interruption. Foreground app remained untouched.")

    if abs(cursor_before[0] - cursor_after[0]) > 2 or abs(cursor_before[1] - cursor_after[1]) > 2:
        logger.warning(
            "Cursor moved slightly (%.1f, %.1f) -> (%.1f, %.1f). Note: User may have moved physical mouse.",
            cursor_before[0],
            cursor_before[1],
            cursor_after[0],
            cursor_after[1],
        )
    else:
        logger.info("VERIFIED: Cursor position preserved.")

    # 9. Save output if requested
    if output_path:
        out_abs = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(out_abs), exist_ok=True)
        with open(out_abs, "w", encoding="utf-8") as f:
            f.write(response_text)
        logger.info("Response saved to %s", out_abs)

    return response_text


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run reliable zero-interruption Gemini desktop automation in background."
    )
    parser.add_argument("--file", "-f", "--video", "-v", dest="file", help="Path to local file (video, image, pdf, audio, etc.)")
    parser.add_argument("--prompt", "-p", required=True, help="Prompt text for Gemini")
    parser.add_argument("--out", "-o", help="Optional output text file path")
    parser.add_argument("--new-chat", action="store_true", help="Start in a new chat")
    parser.add_argument("--json", action="store_true", help="Print result as JSON envelope")

    args = parser.parse_args()

    try:
        response = run_gemini_workflow(
            prompt=args.prompt,
            file_path=args.file,
            output_path=args.out,
            new_chat=args.new_chat,
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "ok": True,
                        "file": args.file,
                        "prompt": args.prompt,
                        "response": response,
                    },
                    indent=2,
                )
            )
        else:
            print("\n=== Gemini Response ===\n")
            print(response)
    except Exception as e:
        logger.error("Automation failed: %s", e)
        if args.json:
            print(json.dumps({"ok": False, "error": str(e)}, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
