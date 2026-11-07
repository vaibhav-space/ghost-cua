#!/usr/bin/env python3
"""
GhostCUA: Meta AI Desktop Background Automation Engine
Target: Meta AI macOS Desktop Application (com.meta.endo.vanilla)

Zero-Interruption Guarantees:
- 0 Cursor Movement
- 0 Focus Theft (Foreground app remains untouched)
- 0 Space/Desktop Switching
- 0 Window Resizing/Minimizing
- Native Thinking Mode Support
- Lossless Clipboard Restoration
"""

import os
import sys
import time
import struct
import logging
import argparse
import json
from typing import Any, Optional

from AppKit import (
    NSPasteboard,
    NSPasteboardTypeString,
    NSRunningApplication,
    NSWorkspace,
)
from Foundation import NSURL
from ApplicationServices import (
    AXUIElementCreateApplication,
    AXUIElementCopyAttributeValue,
    AXUIElementSetAttributeValue,
    AXUIElementPerformAction,
    kAXErrorSuccess,
)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("meta_ai_background")

BUNDLE_ID = "com.meta.endo.vanilla"


class BackgroundAutomationError(Exception):
    """Raised when an automation invariant fails."""


def get_meta_ai_pid() -> int:
    apps = NSRunningApplication.runningApplicationsWithBundleIdentifier_(BUNDLE_ID)
    if not apps:
        raise BackgroundAutomationError(
            f"Meta AI desktop application ({BUNDLE_ID}) is not currently running. "
            "Please launch Meta AI first."
        )
    return apps[0].processIdentifier()


def get_meta_ai_main_window(ax_app: Any, timeout: float = 10.0) -> Any:
    start = time.time()
    while time.time() - start < timeout:
        for attr in ("AXMainWindow", "AXFocusedWindow"):
            err, win = AXUIElementCopyAttributeValue(ax_app, attr, None)
            if err == kAXErrorSuccess and win is not None:
                return win

        err, wins = AXUIElementCopyAttributeValue(ax_app, "AXWindows", None)
        if err == kAXErrorSuccess and wins and len(wins) > 0:
            return wins[0]

        time.sleep(0.5)

    raise BackgroundAutomationError("Could not resolve Meta AI main window via Accessibility.")


def find_element_by_id(el: Any, target_id: str, depth: int = 0, max_depth: int = 25) -> Any:
    if depth > max_depth:
        return None
    _, ax_id = AXUIElementCopyAttributeValue(el, "AXIdentifier", None)
    if ax_id == target_id:
        return el

    _, children = AXUIElementCopyAttributeValue(el, "AXChildren", None)
    if children:
        for c in children:
            res = find_element_by_id(c, target_id, depth + 1, max_depth)
            if res:
                return res
    return None


def find_element_by_role_and_desc(
    el: Any, role_target: str, desc_target: str, depth: int = 0, max_depth: int = 30
) -> Any:
    if depth > max_depth:
        return None
    _, role = AXUIElementCopyAttributeValue(el, "AXRole", None)
    _, desc = AXUIElementCopyAttributeValue(el, "AXDescription", None)
    if role == role_target and str(desc or "").strip().lower() == desc_target.lower():
        return el

    _, children = AXUIElementCopyAttributeValue(el, "AXChildren", None)
    if children:
        for c in children:
            res = find_element_by_role_and_desc(c, role_target, desc_target, depth + 1, max_depth)
            if res:
                return res
    return None


def ensure_thinking_mode(win: Any) -> None:
    """Ensure Meta AI is in 'Thinking' mode for deep research."""
    picker = find_element_by_id(win, "composer-model-picker")
    if not picker:
        return
    _, desc = AXUIElementCopyAttributeValue(picker, "AXDescription", None)
    if desc and "thinking" in str(desc).lower():
        logger.info("Thinking mode is already active.")
        return

    logger.info("Activating Thinking mode in model picker...")
    AXUIElementPerformAction(picker, "AXPress")
    time.sleep(0.5)
    # Re-find menu item or toggle
    thinking_opt = find_element_by_role_and_desc(win, "AXMenuItem", "Thinking")
    if thinking_opt:
        AXUIElementPerformAction(thinking_opt, "AXPress")
        time.sleep(0.5)
        logger.info("Thinking mode selected.")


def start_new_chat(win: Any) -> None:
    """Click 'New chat' button to reset composer."""
    new_chat_btn = find_element_by_role_and_desc(win, "AXButton", "New chat")
    if new_chat_btn:
        logger.info("Resetting composer via background 'New chat' action...")
        AXUIElementPerformAction(new_chat_btn, "AXPress")
        time.sleep(0.8)


def enter_prompt_background(win: Any, prompt_text: str, timeout: float = 10.0) -> None:
    logger.info("Injecting prompt text via native accessibility...")
    start = time.time()
    while time.time() - start < timeout:
        scroll = find_element_by_id(win, "chat-composer-input")
        if scroll:
            _, children = AXUIElementCopyAttributeValue(scroll, "AXChildren", None)
            if children:
                for c in children:
                    _, role = AXUIElementCopyAttributeValue(c, "AXRole", None)
                    if role == "AXTextArea":
                        err = AXUIElementSetAttributeValue(c, "AXValue", prompt_text)
                        if err == kAXErrorSuccess:
                            logger.info("Prompt text injected successfully into AXTextArea.")
                            time.sleep(0.4)
                            return
                        else:
                            logger.warning("AXUIElementSetAttributeValue error: %d", err)
        time.sleep(0.5)

    raise BackgroundAutomationError("Could not locate Meta AI composer AXTextArea.")


def submit_request_background(win: Any, timeout: float = 15.0) -> None:
    """
    Submits prompt and verifies that submission succeeded
    by confirming composer text clears or stop button appears.
    """
    logger.info("Submitting request via background AXPress on Send button...")
    start = time.time()

    while time.time() - start < timeout:
        stop_btn = find_element_by_id(win, "chat-stop")
        if stop_btn:
            logger.info("Submission confirmed: Generation started (chat-stop present).")
            return

        send_btn = find_element_by_id(win, "chat-send")
        if send_btn:
            AXUIElementPerformAction(send_btn, "AXPress")
            logger.info("Triggered AXPress on Send button. Verifying composer clearance...")
            time.sleep(1.0)

            # Check if text cleared
            scroll = find_element_by_id(win, "chat-composer-input")
            if scroll:
                _, children = AXUIElementCopyAttributeValue(scroll, "AXChildren", None)
                if children:
                    for c in children:
                        _, role = AXUIElementCopyAttributeValue(c, "AXRole", None)
                        if role == "AXTextArea":
                            _, val = AXUIElementCopyAttributeValue(c, "AXValue", None)
                            if not str(val or "").strip():
                                logger.info("Submission confirmed: Composer text cleared.")
                                return
        time.sleep(0.5)

    raise BackgroundAutomationError("Could not confirm Meta AI submission within timeout.")


def wait_for_generation_complete(ax_app: Any, timeout: float = 360.0) -> None:
    """Monitors generation lifecycle until chat-stop disappears."""
    logger.info("Monitoring generation state in background (timeout: %.0fs)...", timeout)
    start = time.time()

    # Initial grace period for generation to register
    time.sleep(1.0)
    last_log = time.time()

    while time.time() - start < timeout:
        win = get_meta_ai_main_window(ax_app)
        stop_btn = find_element_by_id(win, "chat-stop")
        if not stop_btn:
            logger.info("Generation complete (chat-stop button disappeared).")
            time.sleep(0.5)
            return
            
        if time.time() - last_log >= 15.0:
            logger.info("Thinking mode in progress... (elapsed: %.0fs)", time.time() - start)
            last_log = time.time()
            
        time.sleep(1.0)

    raise BackgroundAutomationError(f"Meta AI generation timed out after {timeout}s.")


def extract_response(win: Any) -> str:
    """
    Extracts response losslessly via the native Copy button
    while preserving the user's pre-existing clipboard.
    """
    logger.info("Extracting response via Copy button...")
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
        # Find all Copy buttons (take the last one corresponding to the newest turn)
        copy_btns: list[Any] = []

        def collect_copy_buttons(el: Any, depth: int = 0) -> None:
            if depth > 25:
                return
            _, role = AXUIElementCopyAttributeValue(el, "AXRole", None)
            _, desc = AXUIElementCopyAttributeValue(el, "AXDescription", None)
            if role == "AXButton" and str(desc or "").strip().lower() == "copy":
                copy_btns.append(el)
            _, children = AXUIElementCopyAttributeValue(el, "AXChildren", None)
            if children:
                for c in children:
                    collect_copy_buttons(c, depth + 1)

        collect_copy_buttons(win)

        if not copy_btns:
            raise BackgroundAutomationError("Could not locate Copy button in Meta AI chat.")

        latest_copy_btn = copy_btns[-1]
        err = AXUIElementPerformAction(latest_copy_btn, "AXPress")
        if err != kAXErrorSuccess:
            raise BackgroundAutomationError(f"Failed to press Copy button: error code {err}")

        time.sleep(0.4)
        response_text = pb.stringForType_(NSPasteboardTypeString)
        if not response_text:
            raise BackgroundAutomationError("Clipboard did not receive text from Copy button.")

        return response_text

    finally:
        # 2. Restore user clipboard
        pb.clearContents()
        for t, data in old_data.items():
            pb.setData_forType_(data, t)


def run_meta_ai_query(
    prompt: str,
    output_path: Optional[str] = None,
    new_chat: bool = False,
    ensure_thinking: bool = True,
    timeout: float = 360.0,
) -> str:
    ws = NSWorkspace.sharedWorkspace()
    front_app_before = ws.frontmostApplication()
    front_id_before = front_app_before.bundleIdentifier() if front_app_before else None

    logger.info("Initial State | Frontmost: %s", front_id_before)

    pid = get_meta_ai_pid()
    ax_app = AXUIElementCreateApplication(pid)
    win = get_meta_ai_main_window(ax_app)

    if new_chat:
        start_new_chat(win)
        win = get_meta_ai_main_window(ax_app)

    if ensure_thinking:
        ensure_thinking_mode(win)

    start_time = time.time()
    enter_prompt_background(win, prompt)
    submit_request_background(win)
    wait_for_generation_complete(ax_app, timeout=timeout)

    win = get_meta_ai_main_window(ax_app)
    response_text = extract_response(win)
    elapsed = time.time() - start_time

    logger.info("Workflow completed in %.2fs. Response length: %d chars", elapsed, len(response_text))

    front_app_after = ws.frontmostApplication()
    front_id_after = front_app_after.bundleIdentifier() if front_app_after else None
    logger.info("Final State | Frontmost: %s", front_id_after)

    if front_id_before == front_id_after:
        logger.info("VERIFIED: Zero focus interruption. Foreground app remained untouched.")
    else:
        logger.warning("Focus changed: %s -> %s", front_id_before, front_id_after)

    if output_path:
        abs_out = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(abs_out), exist_ok=True)
        with open(abs_out, "w", encoding="utf-8") as f:
            f.write(response_text)
        logger.info("Response saved to %s", abs_out)

    return response_text


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run reliable zero-interruption Meta AI desktop automation in background."
    )
    parser.add_argument("--prompt", "-p", required=True, help="Research prompt or query for Meta AI")
    parser.add_argument("--out", "-o", default=None, help="Optional output text file path")
    parser.add_argument("--new-chat", action="store_true", help="Start in a fresh chat session")
    parser.add_argument(
        "--no-thinking", action="store_true", help="Disable automatic Thinking mode verification"
    )
    parser.add_argument(
        "--timeout", "-t", type=float, default=360.0, help="Maximum timeout in seconds for generation (default: 360)"
    )
    parser.add_argument("--json", action="store_true", help="Print result as structured JSON envelope")

    args = parser.parse_args()

    try:
        response = run_meta_ai_query(
            prompt=args.prompt,
            output_path=args.out,
            new_chat=args.new_chat,
            ensure_thinking=not args.no_thinking,
            timeout=args.timeout,
        )

        if args.json:
            result = {
                "ok": True,
                "app": "Meta AI",
                "prompt": args.prompt,
                "response": response,
            }
            print(json.dumps(result, indent=2))
        else:
            print(response)

    except Exception as e:
        logger.error("Automation error: %s", e)
        if args.json:
            print(json.dumps({"ok": False, "error": str(e)}, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
