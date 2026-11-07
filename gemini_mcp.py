#!/usr/bin/env python3
"""
gemini_mcp.py - MCP Server for Universal Zero-Interruption Background Gemini Desktop Automation
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gemini_background as gb

server = Server("gemini-desktop-automation")

TOOL_DEFS = [
    Tool(
        name="gemini_query",
        description=(
            "Query the native macOS Gemini desktop application completely in the background. "
            "Runs with 0 cursor movement, 0 focus theft, and 0 window or Space switching. "
            "Supports text-only queries or attaching any supported local file (videos, images, PDFs, docs, audio). "
            "Extracts complete response losslessly while preserving user clipboard."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The prompt or question for Gemini",
                },
                "file_path": {
                    "type": "string",
                    "description": "Optional path to a local file to attach (video, image, pdf, etc.)",
                },
                "video_path": {
                    "type": "string",
                    "description": "Alias for file_path (for backward compatibility)",
                },
                "output_path": {
                    "type": "string",
                    "description": "Optional local file path to save the response text",
                },
                "new_chat": {
                    "type": "boolean",
                    "description": "Whether to reset to a new chat before submitting (default: false)",
                    "default": False,
                },
            },
            "required": ["prompt"],
            "additionalProperties": False,
        },
    )
]


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return TOOL_DEFS


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    if name not in ("gemini_query", "gemini_video_query"):
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    args = arguments or {}
    prompt = args.get("prompt")
    file_path = args.get("file_path") or args.get("video_path")
    output_path = args.get("output_path")
    new_chat = bool(args.get("new_chat", False))

    if not prompt:
        return [
            TextContent(
                type="text",
                text=json.dumps({"ok": False, "error": "'prompt' is required."}, indent=2),
            )
        ]

    loop = asyncio.get_running_loop()
    try:
        response_text = await loop.run_in_executor(
            None,
            gb.run_gemini_workflow,
            prompt,
            file_path,
            output_path,
            new_chat,
        )
        result = {
            "ok": True,
            "prompt": prompt,
            "file_path": os.path.abspath(file_path) if file_path else None,
            "output_path": os.path.abspath(output_path) if output_path else None,
            "response": response_text,
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as exc:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"ok": False, "error": str(exc)},
                    indent=2,
                ),
            )
        ]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
