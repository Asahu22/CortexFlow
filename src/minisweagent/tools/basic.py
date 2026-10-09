"""Basic, safe local tools: read_file and write_file.

Both tools are synchronous and return a dict matching the environment
execute result shape: {"output": str, "returncode": int}.

Safety considerations (kept simple on purpose for a starter set):
- Paths are resolved to absolute paths.
- write_file creates parent directories as needed.
"""

from __future__ import annotations

import ast
import base64
import shlex
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

from . import register


@dataclass
class ReadFile:
    name: str = "read_file"
    description: str = "Read a UTF-8 text file. Optionally specify line ranges."
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to read"},
                "start_line": {"type": "integer", "description": "Starting line number (1-indexed, optional)"},
                "end_line": {"type": "integer", "description": "Ending line number (1-indexed, optional)"},
            },
            "required": ["path"],
            "additionalProperties": False,
        }
    )

    def __call__(self, args: dict, env=None) -> dict:
        path_arg = str(args.get("path", ""))
        start_line = args.get("start_line")
        end_line = args.get("end_line")

        if not path_arg:
            return {"output": "Missing 'path'", "returncode": 2}

        # Build command for reading specific lines
        if start_line is not None or end_line is not None:
            start = start_line if start_line else 1
            end = end_line if end_line else ""

            if env is not None:
                # Use sed to extract lines in container
                if end:
                    cmd = f"sed -n '{start},{end}p' {shlex.quote(path_arg)}"
                else:
                    cmd = f"sed -n '{start},$p' {shlex.quote(path_arg)}"
                return env.execute(cmd)
            else:
                # Host filesystem
                try:
                    p = Path(path_arg).expanduser().resolve()
                    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
                    if end:
                        selected = lines[start - 1 : end]
                    else:
                        selected = lines[start - 1 :]
                    return {"output": "\n".join(selected), "returncode": 0}
                except FileNotFoundError:
                    return {"output": f"File not found: {path_arg}", "returncode": 2}
                except Exception as e:
                    return {"output": f"Error reading file: {e}", "returncode": 1}

        # Original behavior: read entire file
        if env is not None:
            cmd = f"cat -- {shlex.quote(path_arg)}"
            return env.execute(cmd)

        try:
            p = Path(path_arg).expanduser().resolve()
            content = p.read_text(encoding="utf-8", errors="replace")
            return {"output": content, "returncode": 0}
        except FileNotFoundError:
            return {"output": f"File not found: {path_arg}", "returncode": 2}
        except IsADirectoryError:
            return {"output": f"Is a directory: {path_arg}", "returncode": 21}
        except PermissionError:
            return {"output": f"Permission denied: {path_arg}", "returncode": 13}
        except Exception as e:
            return {"output": f"Error reading file: {e}", "returncode": 1}


@dataclass
class WriteFile:
    name: str = "write_file"
    description: str = "Write content to a UTF-8 text file. Creates parent directories if needed. **Use ONLY for creating new files**. For modifying existing files, use replace_in_file instead."
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to write"},
                "content": {"type": "string", "description": "Content to write to the file"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        }
    )

    def __call__(self, args: dict, env=None) -> dict:
        path_arg = str(args.get("path", ""))
        content = args.get("content", "")

        if not path_arg:
            return {"output": "Missing 'path'", "returncode": 2}

        if env is not None:
            encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
            cmd = f"mkdir -p $(dirname {shlex.quote(path_arg)}) && echo {shlex.quote(encoded)} | base64 -d > {shlex.quote(path_arg)}"
            return env.execute(cmd)

        try:
            p = Path(path_arg).expanduser().resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return {"output": f"Successfully wrote to {path_arg}", "returncode": 0}
        except PermissionError:
            return {"output": f"Permission denied: {path_arg}", "returncode": 13}
        except Exception as e:
            return {"output": f"Error writing file: {e}", "returncode": 1}


@dataclass
class SearchFile:
    name: str = "search_file"
    description: str = "Search for a pattern in a file and show matching lines with line numbers and context."
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to search"},
                "pattern": {"type": "string", "description": "Pattern to search for"},
                "context_lines": {
                    "type": "integer",
                    "description": "Number of context lines before/after match (default: 2)",
                },
            },
            "required": ["path", "pattern"],
            "additionalProperties": False,
        }
    )

    def __call__(self, args: dict, env=None) -> dict:
        path_arg = str(args.get("path", ""))
        pattern = str(args.get("pattern", ""))
        context = args.get("context_lines", 2)

        if not path_arg:
            return {"output": "Missing 'path'", "returncode": 2}
        if not pattern:
            return {"output": "Missing 'pattern'", "returncode": 2}

        # Use grep with line numbers and context
        # -n: line numbers, -C: context lines, -F: fixed string (safer)
        cmd = f"grep -n -C {context} -F {shlex.quote(pattern)} {shlex.quote(path_arg)}"

        if env is not None:
            result = env.execute(cmd)
            # grep returns 1 if no matches found, which is not really an error
            if result["returncode"] == 1 and not result["output"]:
                result["output"] = f"No matches found for '{pattern}' in {path_arg}"
                result["returncode"] = 0
            return result

        # Host filesystem
        try:
            import subprocess

            result = subprocess.run(
                ["grep", "-n", "-C", str(context), "-F", pattern, path_arg],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return {"output": result.stdout, "returncode": 0}
            elif result.returncode == 1:
                return {"output": f"No matches found for '{pattern}' in {path_arg}", "returncode": 0}
            else:
                return {"output": result.stderr or "Search failed", "returncode": result.returncode}
        except FileNotFoundError:
            return {"output": f"File not found: {path_arg}", "returncode": 2}
        except Exception as e:
            return {"output": f"Error searching file: {e}", "returncode": 1}


@dataclass
class ListFiles:
    name: str = "list_files"
    description: str = "List files in a directory, optionally filtered by pattern (e.g., '*.py')."
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path (default: current directory)"},
                "pattern": {"type": "string", "description": "Pattern to filter files (e.g., '*.py', optional)"},
                "recursive": {"type": "boolean", "description": "Search recursively (default: false)"},
            },
            "required": [],
            "additionalProperties": False,
        }
    )

    def __call__(self, args: dict, env=None) -> dict:
        path_arg = str(args.get("path", "."))
        pattern = args.get("pattern", "*")
        recursive = args.get("recursive", False)

        if env is not None:
            # Use find command for better control
            if recursive:
                cmd = f"find {shlex.quote(path_arg)} -type f -name {shlex.quote(pattern)}"
            else:
                # Use ls with wildcard
                if pattern != "*":
                    cmd = f"ls -1 {shlex.quote(path_arg)}/{shlex.quote(pattern)} 2>/dev/null || echo 'No files found'"
                else:
                    cmd = f"ls -1 {shlex.quote(path_arg)}"
            return env.execute(cmd)

        # Host filesystem
        try:
            import fnmatch
            from pathlib import Path

            p = Path(path_arg).expanduser().resolve()

            if not p.exists():
                return {"output": f"Directory not found: {path_arg}", "returncode": 2}
            if not p.is_dir():
                return {"output": f"Not a directory: {path_arg}", "returncode": 20}

            if recursive:
                # Recursive search
                files = [str(f.relative_to(p)) for f in p.rglob(pattern) if f.is_file()]
            else:
                # Single directory
                files = [f.name for f in p.iterdir() if f.is_file() and fnmatch.fnmatch(f.name, pattern)]

            if not files:
                return {"output": f"No files found matching '{pattern}' in {path_arg}", "returncode": 0}

            files.sort()
            return {"output": "\n".join(files), "returncode": 0}

        except PermissionError:
            return {"output": f"Permission denied: {path_arg}", "returncode": 13}
        except Exception as e:
            return {"output": f"Error listing files: {e}", "returncode": 1}


@dataclass
class ReadManyFiles:
    name: str = "read_many_files"
    description: str = (
        "Read and concatenate the content of multiple UTF-8 text files. Provides succinct representation."
    )
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "paths": {"type": "array", "items": {"type": "string"}, "description": "A list of file paths to read"},
            },
            "required": ["paths"],
            "additionalProperties": False,
        }
    )

    def __call__(self, args: dict, env=None) -> dict:
        paths_arg = args.get("paths", [])
        if not isinstance(paths_arg, list) or not paths_arg:
            return {"output": "Missing 'paths' or 'paths' is not a list", "returncode": 2}

        # check if the env is docker or local
        is_container_env = env is not None and "docker" in str(type(env)).lower()

        if is_container_env:
            cmds = []
            for p in paths_arg:
                quoted_p = shlex.quote(p)
                # Linux
                cmds.append(
                    f"(echo '--- START OF {quoted_p} ---' && "
                    f"cat -- {quoted_p} && "
                    f"echo '--- END OF {quoted_p} ---') || "
                    f"echo 'Error: Could not read {quoted_p}'"
                )
            full_cmd = " ; ".join(cmds)
            return env.execute(full_cmd)

        else:
            try:
                full_content = []
                for path_str in paths_arg:
                    # get  correct working directory from the local env
                    if env is not None and hasattr(env, "cwd"):
                        base_path = Path(env.cwd)
                    else:
                        base_path = Path.cwd()  # Fallback

                    # get file path
                    p = (base_path / path_str).expanduser().resolve()

                    full_content.append(f"--- START OF {path_str} ---")
                    try:
                        content = p.read_text(encoding="utf-8", errors="replace")
                        full_content.append(content)
                    except FileNotFoundError:
                        full_content.append(f"Error: File not found: {p}")
                    except IsADirectoryError:
                        full_content.append(f"Error: Is a directory: {p}")
                    except Exception as e:
                        full_content.append(f"Error reading file {p}: {e}")
                    full_content.append(f"--- END OF {path_str} ---")

                return {"output": "\n".join(full_content), "returncode": 0}
            except Exception as e:
                return {"output": f"Error processing files: {e}", "returncode": 1}


@dataclass
class AppendToFile:
    name: str = "append_to_file"
    description: str = "Append a line of content to a UTF-8 text file. Creates parent directories and file if needed."
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to append to (default: todo.txt)"},
                "content": {"type": "string", "description": "Content to append as a new line"},
            },
            "required": ["content"],
            "additionalProperties": False,
        }
    )

    def __call__(self, args: dict, env=None) -> dict:
        path_arg = str(args.get("path", "todo.txt"))
        content = args.get("content")

        if content is None:
            return {"output": "Missing 'content'", "returncode": 2}

        # content is a single line to avoid formatting issues
        content_line = str(content).replace("\n", " ")

        # check if the env is docker or local
        is_container_env = env is not None and "docker" in str(type(env)).lower()

        if is_container_env:
            quoted_path = shlex.quote(path_arg)
            quoted_content = shlex.quote(content_line)
            cmd = f"mkdir -p $(dirname {quoted_path}) && echo {quoted_content} >> {quoted_path}"
            return env.execute(cmd)

        else:
            try:
                # get the correct working directory from the local env
                if env is not None and hasattr(env, "cwd"):
                    base_path = Path(env.cwd)
                else:
                    base_path = Path.cwd()  # Fallback

                # get the file path relative to the agent's CWD
                p = (base_path / path_arg).expanduser().resolve()

                # create parent directories if they don't exist
                p.parent.mkdir(parents=True, exist_ok=True)

                # open in append 'a' mode, create file if it doesn't exist
                with open(p, "a", encoding="utf-8") as f:
                    f.write(content_line + "\n")

                return {"output": f"Successfully appended to {path_arg}", "returncode": 0}

            except PermissionError:
                return {"output": f"Permission denied: {path_arg}", "returncode": 13}
            except IsADirectoryError:
                return {"output": f"Error: Path is a directory: {path_arg}", "returncode": 21}
            except Exception as e:
                return {"output": f"Error appending to file: {e}", "returncode": 1}


@dataclass
class ReplaceInFile:
    name: str = "replace_in_file"
    description: str = (
        "Replace exact text in a file. CRITICAL: For multi-line code blocks, "
        "include the COMPLETE block with all indentation. The old_text must match "
        "EXACTLY including all whitespace. This is the PRIMARY tool for code changes."
    )
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file"},
                "old_text": {"type": "string", "description": "Exact text to replace (must match exactly)"},
                "new_text": {"type": "string", "description": "New text to replace with"},
            },
            "required": ["path", "old_text", "new_text"],
            "additionalProperties": False,
        }
    )

    def __call__(self, args: dict, env=None) -> dict:
        path_arg = str(args.get("path", ""))
        old_text = args.get("old_text", "")
        new_text = args.get("new_text", "")

        if not path_arg or not old_text:
            return {"output": "Missing required parameters", "returncode": 2}

        try:
            if env is not None:
                # Read file first
                read_result = env.execute(f"cat -- {shlex.quote(path_arg)}")
                if read_result["returncode"] != 0:
                    return read_result

                content = read_result["output"]
            else:
                p = Path(path_arg).expanduser().resolve()
                content = p.read_text(encoding="utf-8", errors="replace")

            # Check if old_text exists
            if old_text not in content:
                return {
                    "output": f"Error: old_text not found in {path_arg}. Make sure it matches exactly.",
                    "returncode": 1,
                }

            # Check if old_text appears multiple times
            count = content.count(old_text)
            if count > 1:
                return {
                    "output": f"Error: old_text appears {count} times in {path_arg}. Be more specific.",
                    "returncode": 1,
                }

            # Perform replacement
            new_content = content.replace(old_text, new_text)

            # Write back
            if env is not None:
                encoded = base64.b64encode(new_content.encode("utf-8")).decode("ascii")
                cmd = f"echo {shlex.quote(encoded)} | base64 -d > {shlex.quote(path_arg)}"
                result = env.execute(cmd)
                if result["returncode"] == 0:
                    result["output"] = f"Successfully replaced text in {path_arg}"
                return result
            else:
                p.write_text(new_content, encoding="utf-8")
                return {"output": f"Successfully replaced text in {path_arg}", "returncode": 0}

        except Exception as e:
            return {"output": f"Error: {e}", "returncode": 1}


@dataclass
class InsertLines:
    """Insert lines at a specific position in a file.

    This tool enables precise insertion of text at any line number, complementing
    append_to_file (end only) and replace_in_file (requires pattern match).

    Use cases:
    - Adding imports at the top of a file
    - Inserting function definitions at specific locations
    - Adding code without modifying existing lines
    """

    name: str = "insert_lines"
    description: str = "Insert text at a specific line number in a file. Line numbering is 1-indexed."
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file"},
                "line_number": {
                    "type": "integer",
                    "description": "Line number where content should be inserted (1-indexed). Content is inserted BEFORE this line.",
                },
                "content": {"type": "string", "description": "Content to insert (can contain multiple lines)"},
            },
            "required": ["path", "line_number", "content"],
            "additionalProperties": False,
        }
    )

    def __call__(self, args: dict, env=None) -> dict:
        path_arg = str(args.get("path", ""))
        line_number = args.get("line_number")
        content = args.get("content", "")

        # Validate parameters
        if not path_arg:
            return {"output": "Missing 'path'", "returncode": 2}
        if line_number is None:
            return {"output": "Missing 'line_number'", "returncode": 2}
        if not isinstance(line_number, int) or line_number < 1:
            return {"output": "line_number must be a positive integer", "returncode": 2}

        # Ensure content ends with newline for proper insertion
        if content and not content.endswith("\n"):
            content += "\n"

        # Check if we're in a real container environment (Docker/SWE-bench)
        is_container_env = env is not None and "docker" in str(type(env)).lower()

        if is_container_env:
            # Container environment: use sed for insertion
            # sed's 'i' command inserts BEFORE the given line
            # Escape content for shell safety
            encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")

            # First, read total lines to handle edge cases
            count_cmd = f"wc -l < {shlex.quote(path_arg)}"
            count_result = env.execute(count_cmd)

            if count_result["returncode"] != 0:
                return {"output": f"File not found or not readable: {path_arg}", "returncode": 2}

            try:
                total_lines = int(count_result["output"].strip())
            except ValueError:
                return {"output": "Error determining file length", "returncode": 1}

            # If line_number > total_lines + 1, append to end
            if line_number > total_lines + 1:
                # Append content to end
                append_cmd = f"echo {shlex.quote(encoded)} | base64 -d >> {shlex.quote(path_arg)}"
                result = env.execute(append_cmd)
                if result["returncode"] == 0:
                    num_lines = content.count("\n")
                    result["output"] = f"Inserted {num_lines} line(s) at end of {path_arg} (line {total_lines + 1})"
                return result

            # Use sed to insert at specific line
            # Create temp file with inserted content
            temp_file = f"/tmp/insert_temp_{hash(path_arg)}.txt"
            insert_cmd = (
                f"echo {shlex.quote(encoded)} | base64 -d > {temp_file} && "
                f"sed -i '{line_number}r {temp_file}' {shlex.quote(path_arg)} && "
                f"rm {temp_file}"
            )

            result = env.execute(insert_cmd)
            if result["returncode"] == 0:
                num_lines = content.count("\n")
                result["output"] = f"Inserted {num_lines} line(s) at line {line_number} in {path_arg}"
            return result

        # Host filesystem
        try:
            p = Path(path_arg).expanduser().resolve()

            if not p.exists():
                return {"output": f"File not found: {path_arg}", "returncode": 2}

            # Read existing lines
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)

            # Handle case where file doesn't end with newline
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"

            # Calculate insertion index (0-based)
            insert_index = min(line_number - 1, len(lines))

            # Split content into lines
            new_lines = content.splitlines(keepends=True)

            # Insert the lines
            lines[insert_index:insert_index] = new_lines

            # Write back
            p.write_text("".join(lines), encoding="utf-8")

            return {
                "output": f"Inserted {len(new_lines)} line(s) at line {min(line_number, len(lines) - len(new_lines) + 1)} in {path_arg}",
                "returncode": 0,
            }

        except PermissionError:
            return {"output": f"Permission denied: {path_arg}", "returncode": 13}
        except Exception as e:
            return {"output": f"Error inserting lines: {e}", "returncode": 1}


@dataclass
class CreateDirectory:
    name: str = "create_directory"
    description: str = "Create a new directory. Creates parent directories as needed."
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the directory to create"},
            },
            "required": ["path"],
            "additionalProperties": False,
        }
    )

    def __call__(self, args: dict, env=None) -> dict:
        path_arg = str(args.get("path", ""))

        if not path_arg:
            return {"output": "Missing 'path'", "returncode": 2}

        if env is not None:
            cmd = f"mkdir -p {shlex.quote(path_arg)}"
            return env.execute(cmd)

        try:
            p = Path(path_arg).expanduser().resolve()
            p.mkdir(parents=True, exist_ok=True)
            return {"output": f"Successfully created directory {path_arg}", "returncode": 0}
        except PermissionError:
            return {"output": f"Permission denied: {path_arg}", "returncode": 13}
        except Exception as e:
            return {"output": f"Error creating directory: {e}", "returncode": 1}


@dataclass
class TodoTool:
    name: str = "todo"
    description: str = "Maintain a lightweight in-memory task list for planning during an agent run."
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "Action: add, list, complete, or clear"},
                "task": {"type": "string", "description": "Task text for the add action"},
                "index": {"type": "integer", "description": "1-indexed task number for the complete action"},
            },
            "required": ["action"],
            "additionalProperties": False,
        }
    )
    tasks: list[dict[str, object]] = field(default_factory=list)

    def __call__(self, args: dict, env=None) -> dict:
        action = str(args.get("action", "list")).lower()

        if action == "add":
            task = args.get("task")
            if not task:
                return {"output": "Missing 'task'", "returncode": 2}
            self.tasks.append({"task": str(task), "done": False})
            return {"output": f"Added task {len(self.tasks)}: {task}", "returncode": 0}

        if action == "list":
            if not self.tasks:
                return {"output": "No tasks", "returncode": 0}
            lines = [
                f"{i}. [{'x' if task['done'] else ' '}] {task['task']}" for i, task in enumerate(self.tasks, start=1)
            ]
            return {"output": "\n".join(lines), "returncode": 0}

        if action == "complete":
            index = args.get("index")
            if index is None:
                return {"output": "Missing 'index'", "returncode": 2}
            try:
                task_index = int(index)
            except (TypeError, ValueError):
                return {"output": "Invalid index", "returncode": 1}
            if task_index < 1 or task_index > len(self.tasks):
                return {"output": "Invalid index", "returncode": 1}
            self.tasks[task_index - 1]["done"] = True
            return {"output": f"Completed task {task_index}", "returncode": 0}

        if action == "clear":
            self.tasks.clear()
            return {"output": "Cleared tasks", "returncode": 0}

        return {"output": f"Unknown action: {action}", "returncode": 1}


@dataclass
class CleanupBeforeSubmit:
    name: str = "cleanup_before_submit"
    description: str = "Check git status and show only source code changes, excluding test files."
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action: check (show status), stage (stage only source files)",
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        }
    )

    def __call__(self, args: dict, env=None) -> dict:
        action = args.get("action", "check").lower()

        if env is None:
            return {"output": "This tool requires an environment", "returncode": 1}

        if action == "check":
            cmd = "git status --short && echo '---' && git diff --cached --name-only"
            return env.execute(cmd)

        elif action == "stage":
            cmd = (
                "git reset && "
                "git add -A && "
                "git reset -- '*test*' '*/test*' 'test*' '**/migrations/*' || true && "
                "git status --short"
            )
            return env.execute(cmd)

        return {"output": f"Unknown action: {action}", "returncode": 1}


@dataclass
class EditBlock:
    # A  tool to replace a range of lines.
    name: str = "edit_block"
    description: str = "Replace a range of lines in a file with new content."
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file"},
                "start_line": {"type": "integer", "description": "Start line number (1-indexed, inclusive)"},
                "end_line": {"type": "integer", "description": "End line number (1-indexed, inclusive)"},
                "new_content": {"type": "string", "description": "New content to put in place of the selected lines"},
            },
            "required": ["path", "start_line", "end_line", "new_content"],
            "additionalProperties": False,
        }
    )

    # A python script to run inside container to handle the edit
    _CONTAINER_SCRIPT = textwrap.dedent("""
    import sys, base64
    try:
        path = sys.argv[1]
        start = int(sys.argv[2])
        end = int(sys.argv[3])
        # Decode new content
        new_content = base64.b64decode(sys.argv[4].encode('ascii')).decode('utf-8')
        
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        # Validate bounds
        if start < 1 or start > len(lines) + 1:
            print(f"Error: Start line {start} is out of bounds (file has {len(lines)} lines)")
            sys.exit(1)
            
        # Convert to 0-indexing
        # Replace lines [start-1 : end]
        # If we are adding to the end, handle gracefully
        idx_start = start - 1
        idx_end = end
        
        # Ensure new content ends with newline if it's multiple lines
        if not new_content.endswith('\\n') and len(lines) > 0:
            new_content += '\\n'
            
        # Perform replacement
        lines[idx_start:idx_end] = [new_content]
        
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
            
        print(f"Successfully replaced lines {start}-{end} in {path}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    """)
    _CONTAINER_SCRIPT_B64 = base64.b64encode(_CONTAINER_SCRIPT.encode("utf-8")).decode("ascii")

    def __call__(self, args: dict, env=None) -> dict:
        path_arg = str(args.get("path", ""))
        start_line = args.get("start_line")
        end_line = args.get("end_line")
        new_content = args.get("new_content", "")

        if not path_arg or start_line is None or end_line is None:
            return {"output": "Missing required arguments", "returncode": 2}

        if end_line < start_line:
            return {"output": "Error: end_line must be greater than or equal to start_line", "returncode": 2}
        is_container_env = env is not None and "docker" in str(type(env)).lower()

        if is_container_env:
            # Container
            # send a small python script into the container to do the list slicing.
            content_b64 = base64.b64encode(new_content.encode("utf-8")).decode("ascii")

            cmd = (
                f"python3 -c \"import base64; exec(base64.b64decode('{self._CONTAINER_SCRIPT_B64}'))\" "
                f"{shlex.quote(path_arg)} {start_line} {end_line} {shlex.quote(content_b64)}"
            )
            return env.execute(cmd)

        else:
            # Host
            try:
                if env is not None and hasattr(env, "cwd"):
                    base_path = Path(env.cwd)
                else:
                    base_path = Path.cwd()

                p = (base_path / path_arg).expanduser().resolve()
                if not p.exists():
                    return {"output": f"File not found: {path_arg}", "returncode": 2}

                lines = p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)

                # Bounds check
                if start_line < 1 or start_line > len(lines) + 1:
                    return {"output": f"Error: Start line {start_line} out of bounds.", "returncode": 1}

                # Prepare new content
                if new_content and not new_content.endswith("\n"):
                    new_content += "\n"

                # Logic: Replace lines from start-1 to end
                idx_start = start_line - 1
                idx_end = end_line

                # Python list slice assignment replaces the range with the new items
                new_lines = new_content.splitlines(keepends=True)
                lines[idx_start:idx_end] = new_lines

                p.write_text("".join(lines), encoding="utf-8")
                return {"output": f"Successfully replaced lines {start_line}-{end_line} in {path_arg}", "returncode": 0}

            except Exception as e:
                return {"output": f"Error editing block: {e}", "returncode": 1}


@dataclass
class LintFile:
    name: str = "lint_file"
    description: str = "Check a file for Python syntax errors. Always run this after editing python files."
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the python file to check"},
            },
            "required": ["path"],
            "additionalProperties": False,
        }
    )

    def __call__(self, args: dict, env=None) -> dict:
        path_arg = str(args.get("path", ""))

        if not path_arg:
            return {"output": "Missing 'path'", "returncode": 2}
        is_container_env = env is not None and "docker" in str(type(env)).lower()

        if is_container_env:
            # Container - check syntax
            cmd = f"python3 -m py_compile {shlex.quote(path_arg)}"
            result = env.execute(cmd)
            if result["returncode"] == 0:
                return {"output": "Syntax OK", "returncode": 0}
            else:
                # Error return
                return {
                    "output": f"Syntax Error:\n{result.get('stderr', '')} {result.get('output', '')}",
                    "returncode": 1,
                }

        else:
            # Host
            try:
                if env is not None and hasattr(env, "cwd"):
                    base_path = Path(env.cwd)
                else:
                    base_path = Path.cwd()

                p = (base_path / path_arg).expanduser().resolve()
                content = p.read_text(encoding="utf-8", errors="replace")

                try:
                    ast.parse(content)
                    return {"output": "Syntax OK", "returncode": 0}
                except SyntaxError as e:
                    return {
                        "output": f"Syntax Error in {path_arg}: line {e.lineno}, col {e.offset}: {e.msg}",
                        "returncode": 1,
                    }
                except Exception as e:
                    return {"output": f"Error linting file: {e}", "returncode": 1}
            except Exception as e:
                return {"output": f"System Error: {e}", "returncode": 1}


@dataclass
class SearchDirectory:
    name: str = "search_dir"
    description: str = (
        "Search for a pattern recursively across all files in a directory. "
        "Returns file paths and line numbers where pattern appears. "
        "CRITICAL for finding where functions/classes are defined across the codebase."
    )
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory to search (default: current)"},
                "pattern": {"type": "string", "description": "Text pattern to find"},
                "file_pattern": {"type": "string", "description": "File filter e.g. '*.py' (default: '*.py')"},
            },
            "required": ["pattern"],
            "additionalProperties": False,
        }
    )

    def __call__(self, args: dict, env=None) -> dict:
        path_arg = str(args.get("path", "."))
        pattern = str(args.get("pattern", ""))
        file_pattern = args.get("file_pattern", "*.py")

        if not pattern:
            return {"output": "Missing 'pattern'", "returncode": 2}

        # Limit to 100 results
        cmd = f"grep -r -n --include={shlex.quote(file_pattern)} {shlex.quote(pattern)} {shlex.quote(path_arg)} 2>/dev/null | head -100"

        if env is not None:
            result = env.execute(cmd)
            if result["returncode"] == 1 and not result["output"]:
                result["output"] = f"No matches found for '{pattern}'"
                result["returncode"] = 0
            return result

        try:
            import subprocess

            result = subprocess.run(
                ["grep", "-r", "-n", f"--include={file_pattern}", pattern, path_arg],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                lines = result.stdout.split("\n")[:100]
                return {"output": "\n".join(lines), "returncode": 0}
            else:
                return {"output": "No matches found", "returncode": 0}
        except Exception as e:
            return {"output": f"Error: {e}", "returncode": 1}


@dataclass
class ValidationScript:
    name: str = "validation_script"
    description: str = (
        "Create and execute a validation script to test feature implementations. "
        "Validates that code changes work as intended against PR requirements. "
        "Returns test results and any errors encountered. "
        "Script should use assertions and print 'REQUIREMENT: <name> PASSED' for each requirement."
    )
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "script_path": {"type": "string", "description": "Path where the validation script will be created"},
                "script_content": {"type": "string", "description": "Python script content to execute for validation"},
                "requirements": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of requirements to validate. Script should print 'REQUIREMENT: <req_name> PASSED' for each met requirement.",
                },
            },
            "required": ["script_path", "script_content"],
            "additionalProperties": False,
        }
    )

    def __call__(self, args: dict, env=None) -> dict:
        script_path = str(args.get("script_path", ""))
        script_content = str(args.get("script_content", ""))
        requirements = args.get("requirements", [])

        if not script_path:
            return {"output": "Missing 'script_path'", "returncode": 2}
        if not script_content:
            return {"output": "Missing 'script_content'", "returncode": 2}

        try:
            # Check if we're in a container environment
            is_container_env = env is not None and "docker" in str(type(env)).lower()

            if is_container_env:
                # In container, write to a temp location and execute
                script_full_path = f"/tmp/{Path(script_path).name}"

                # Encode script content for safe transmission
                encoded_script = base64.b64encode(script_content.encode("utf-8")).decode("ascii")

                # Write script and execute in container
                cmd = (
                    f"echo {shlex.quote(encoded_script)} | base64 -d > {shlex.quote(script_full_path)} && "
                    f"python {shlex.quote(script_full_path)} ; "
                    f"rm -f {shlex.quote(script_full_path)}"
                )
                result = env.execute(cmd)
                result["script_path"] = script_full_path
                return result
            else:
                # Host filesystem
                p = Path(script_path).expanduser().resolve()
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(script_content, encoding="utf-8")

                # Run on host filesystem
                import subprocess
                import sys

                result = subprocess.run(
                    [sys.executable, str(p)],
                    capture_output=True,
                    text=True,
                    cwd=str(p.parent),
                    timeout=30,
                )

                output = result.stdout
                if result.stderr:
                    output += "\nSTDERR:\n" + result.stderr

                # Validate requirements if provided
                if requirements:
                    validation_summary = "\n\n=== Requirement Validation ===\n"
                    for req in requirements:
                        # Check if this requirement was explicitly marked as passed
                        req_pattern = f"REQUIREMENT: {req} PASSED"
                        if req_pattern in output:
                            validation_summary += f"✓ {req}\n"
                        else:
                            validation_summary += f"✗ {req}\n"
                    output += validation_summary

                return {
                    "output": output,
                    "returncode": result.returncode,
                    "script_path": str(p),
                }
        except subprocess.TimeoutExpired:
            return {"output": "Script execution timed out (30 seconds)", "returncode": 124}
        except PermissionError:
            return {"output": f"Permission denied: {script_path}", "returncode": 13}
        except Exception as e:
            return {"output": f"Error executing validation script: {e}", "returncode": 1}


# Register defaults on import for convenience
register(ReadFile())
register(WriteFile())
register(SearchFile())
register(ListFiles())
register(ReadManyFiles())
register(AppendToFile())
register(ReplaceInFile())
register(InsertLines())
register(CreateDirectory())
register(TodoTool())
register(CleanupBeforeSubmit())
register(EditBlock())
register(LintFile())
register(SearchDirectory())
register(ValidationScript())
