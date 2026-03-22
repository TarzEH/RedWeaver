"""File reader tool for CrewAI agents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class FileReaderInput(BaseModel):
    """Input schema for file read operations."""

    file_path: str = Field(description="Path to the file to read.")
    start_line: int = Field(default=0, description="Start reading from this line (0 = beginning).")
    end_line: int = Field(default=0, description="Stop reading at this line (0 = end of file).")


class FileReaderTool(BaseTool):
    """Read the contents of a file.

    Supports reading full files or specific line ranges.
    Truncates output for very large files.
    """

    name: str = "file_reader"
    description: str = (
        "Read the contents of a file. "
        "Optionally specify start_line and end_line to read a specific range."
    )
    args_schema: Type[BaseModel] = FileReaderInput

    def _run(
        self,
        file_path: str,
        start_line: int = 0,
        end_line: int = 0,
    ) -> str:
        try:
            path = Path(file_path)
            if not path.exists():
                return json.dumps({"status": "failed", "error": f"File not found: {file_path}"})
            if not path.is_file():
                return json.dumps({"status": "failed", "error": f"Not a file: {file_path}"})

            content = path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines(keepends=True)
            total_lines = len(lines)

            # Apply line range
            if start_line > 0 or end_line > 0:
                s = max(0, start_line - 1)  # Convert to 0-indexed
                e = end_line if end_line > 0 else total_lines
                lines = lines[s:e]
                content = "".join(lines)

            # Truncate large outputs
            max_chars = 15_000
            truncated = False
            if len(content) > max_chars:
                content = content[:max_chars]
                truncated = True

            result = {
                "status": "success",
                "file_path": file_path,
                "total_lines": total_lines,
                "content": content,
            }
            if truncated:
                result["truncated"] = True
                result["message"] = f"Output truncated to {max_chars} chars"

            return json.dumps(result)

        except Exception as e:
            return json.dumps({"status": "failed", "error": str(e)})
