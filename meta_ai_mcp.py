#!/usr/bin/env python3
"""
GhostCUA: Meta AI MCP Server
Exposes background Meta AI research to MCP-compatible coding agents
(Claude Code, Cursor, Zed, Codex, Antigravity).
"""

import sys
import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP
from meta_ai_background import run_meta_ai_query, BackgroundAutomationError

# Configure logging to stderr for stdio MCP compliance
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger("meta_ai_mcp")

mcp = FastMCP("ghost-cua-meta-ai")


@mcp.tool()
def meta_ai_research(
    prompt: str,
    output_path: Optional[str] = None,
    new_chat: bool = True,
    ensure_thinking: bool = True,
    timeout: float = 360.0,
) -> str:
    """
    Run deep research via the official Meta AI macOS desktop application in the background.
    Ideal for querying live Instagram trends, creator engagement, audience sentiment,
    and open-ended multi-step synthesis using Meta AI's Thinking model.

    Guarantees:
    - Zero user interruption: 0 mouse movement, 0 focus theft, 0 Space switches.
    - Operates completely in the background while the user continues working.

    Args:
        prompt: Research query or instructions for Meta AI.
        output_path: (Optional) Path to save the extracted response text.
        new_chat: (Optional) Whether to click 'New chat' to start in a fresh session (default: True).
        ensure_thinking: (Optional) Whether to verify Thinking mode is active (default: True).
        timeout: (Optional) Maximum generation timeout in seconds (default: 360.0).

    Returns:
        The complete research report synthesized by Meta AI.
    """
    logger.info("Executing meta_ai_research tool (Thinking=%s)...", ensure_thinking)
    try:
        response = run_meta_ai_query(
            prompt=prompt,
            output_path=output_path,
            new_chat=new_chat,
            ensure_thinking=ensure_thinking,
            timeout=timeout,
        )
        return response
    except BackgroundAutomationError as e:
        logger.error("Meta AI automation failed: %s", e)
        return f"Error: Meta AI background automation failed: {e}"
    except Exception as e:
        logger.error("Unexpected error in meta_ai_research: %s", e)
        return f"Error: {e}"


def main():
    logger.info("Starting GhostCUA Meta AI MCP server (stdio)...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
