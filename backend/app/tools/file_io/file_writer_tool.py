"""File writer tool for CrewAI agents.

Allows agents to create, overwrite, append to, or patch files
within the project directory. Includes automatic backup and
path validation.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from app.tools.file_io.safety import PathValidator


class FileWriterInput(BaseModel):
    """Input schema for file write operations."""

    file_path: str = Field(description="Path to the file to write or modify.")
    content: str = Field(description="Content to write, append, or use as replacement text.")
    mode: str = Field(
        default="write",
        description="Operation mode: 'write' (create/overwrite), 'append' (add to end), 'patch' (find and replace).",
    )
    find_text: str = Field(
        default="",
        description="Text to find when using 'patch' mode. Will be replaced by 'content'.",
    )
    backup: bool = Field(
        default=True,
        description="Create a .bak backup before modifying existing files.",
    )


class FileWriterTool(BaseTool):
    """Write or modify files in the project.

    Supports three modes:
    - write: Create a new file or overwrite existing content
    - append: Add content to the end of a file
    - patch: Find and replace specific text in a file
    """

    name: str = "file_writer"
    description: str = (
        "Write or modify files in the project. "
        "Modes: 'write' (create/overwrite), 'append' (add to end), "
        "'patch' (find and replace text). "
        "Only works within allowed project directories."
    )
    args_schema: Type[BaseModel] = FileWriterInput

    def _run(
        self,
        file_path: str,
        content: str,
        mode: str = "write",
        find_text: str = "",
        backup: bool = True,
    ) -> str:
        try:
            validated_path = PathValidator.validate(file_path)

            # Create parent directories if needed
            os.makedirs(os.path.dirname(validated_path), exist_ok=True)

            # Backup existing file
            if backup and os.path.exists(validated_path):
                shutil.copy2(validated_path, validated_path + ".bak")

            if mode == "write":
                Path(validated_path).write_text(content, encoding="utf-8")
                return json.dumps({
                    "status": "success",
                    "operation": "write",
                    "file_path": file_path,
                    "bytes_written": len(content.encode("utf-8")),
                })

            elif mode == "append":
                with open(validated_path, "a", encoding="utf-8") as f:
                    f.write(content)
                return json.dumps({
                    "status": "success",
                    "operation": "append",
                    "file_path": file_path,
                    "bytes_appended": len(content.encode("utf-8")),
                })

            elif mode == "patch":
                if not find_text:
                    return json.dumps({
                        "status": "failed",
                        "error": "find_text is required for patch mode.",
                    })
                existing = Path(validated_path).read_text(encoding="utf-8")
                if find_text not in existing:
                    return json.dumps({
                        "status": "failed",
                        "error": f"find_text not found in {file_path}.",
                    })
                updated = existing.replace(find_text, content, 1)
                Path(validated_path).write_text(updated, encoding="utf-8")
                return json.dumps({
                    "status": "success",
                    "operation": "patch",
                    "file_path": file_path,
                    "replacements": 1,
                })

            else:
                return json.dumps({
                    "status": "failed",
                    "error": f"Unknown mode: {mode}. Use 'write', 'append', or 'patch'.",
                })

        except (ValueError, PermissionError) as e:
            return json.dumps({"status": "failed", "error": str(e)})
        except Exception as e:
            return json.dumps({"status": "failed", "error": str(e)})
