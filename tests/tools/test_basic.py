# ReadFile Tests
def test_register_and_use_read_write_file(tmp_path):
    # Import registers tools into REGISTRY
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    assert "read_file" in REGISTRY
    assert "write_file" in REGISTRY

    write = REGISTRY["write_file"]
    read = REGISTRY["read_file"]

    target = tmp_path / "example.txt"
    content = "hello world"

    # Write
    res_w = write({"path": str(target), "content": content})
    assert res_w["returncode"] == 0
    assert target.exists()
    assert target.read_text(encoding="utf-8") == content

    # Read
    res_r = read({"path": str(target)})
    assert res_r["returncode"] == 0
    assert res_r["output"] == content


def test_read_nonexistent(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    read = REGISTRY["read_file"]
    res = read({"path": str(tmp_path / "nope.txt")})
    assert res["returncode"] != 0
    assert "not found" in res["output"].lower()


def test_read_file_with_line_range(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    read = REGISTRY["read_file"]

    # Create file with multiple lines
    test_file = tmp_path / "lines.txt"
    test_file.write_text("line1\nline2\nline3\nline4\nline5\n")

    # Read lines 2-4
    res = read({"path": str(test_file), "start_line": 2, "end_line": 4})
    assert res["returncode"] == 0
    assert "line2" in res["output"]
    assert "line3" in res["output"]
    assert "line4" in res["output"]
    assert "line1" not in res["output"]
    assert "line5" not in res["output"]


def test_read_file_directory_error(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    read = REGISTRY["read_file"]
    res = read({"path": str(tmp_path)})
    assert res["returncode"] != 0
    assert "directory" in res["output"].lower()


def test_read_file_missing_path(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    read = REGISTRY["read_file"]
    res = read({"path": ""})
    assert res["returncode"] == 2
    assert "Missing 'path'" in res["output"]


# WriteFile Tests
def test_write_file_creates_directories(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    write = REGISTRY["write_file"]

    nested_path = tmp_path / "sub1" / "sub2" / "file.txt"
    content = "test content"

    res = write({"path": str(nested_path), "content": content})
    assert res["returncode"] == 0
    assert nested_path.exists()
    assert nested_path.read_text() == content


def test_write_file_overwrites(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    write = REGISTRY["write_file"]

    test_file = tmp_path / "test.txt"
    test_file.write_text("original")

    res = write({"path": str(test_file), "content": "new content"})
    assert res["returncode"] == 0
    assert test_file.read_text() == "new content"


def test_write_file_missing_path(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    write = REGISTRY["write_file"]
    res = write({"path": "", "content": "test"})
    assert res["returncode"] == 2
    assert "Missing 'path'" in res["output"]


# SearchFile Tests
def test_search_file_basic(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    search = REGISTRY["search_file"]

    test_file = tmp_path / "search.txt"
    test_file.write_text("line1\nfind me\nline3\nline4\n")

    res = search({"path": str(test_file), "pattern": "find me"})
    assert res["returncode"] == 0
    assert "find me" in res["output"]


def test_search_file_with_context(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    search = REGISTRY["search_file"]

    test_file = tmp_path / "context.txt"
    test_file.write_text("line1\nline2\nMATCH\nline4\nline5\n")

    res = search({"path": str(test_file), "pattern": "MATCH", "context_lines": 1})
    assert res["returncode"] == 0
    assert "MATCH" in res["output"]
    # Should include context lines
    assert "line2" in res["output"]
    assert "line4" in res["output"]


def test_search_file_no_matches(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    search = REGISTRY["search_file"]

    test_file = tmp_path / "nomatch.txt"
    test_file.write_text("some content\n")

    res = search({"path": str(test_file), "pattern": "not_here"})
    assert res["returncode"] == 0
    assert "No matches found" in res["output"]


def test_search_file_missing_params(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    search = REGISTRY["search_file"]

    # Missing pattern
    res = search({"path": str(tmp_path / "test.txt"), "pattern": ""})
    assert res["returncode"] == 2
    assert "Missing 'pattern'" in res["output"]

    # Missing path
    res = search({"path": "", "pattern": "test"})
    assert res["returncode"] == 2
    assert "Missing 'path'" in res["output"]


# ListFiles Tests
def test_list_files_basic(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    list_files = REGISTRY["list_files"]

    # Create test files
    (tmp_path / "file1.txt").write_text("a")
    (tmp_path / "file2.py").write_text("b")

    res = list_files({"path": str(tmp_path)})
    assert res["returncode"] == 0
    assert "file1.txt" in res["output"]
    assert "file2.py" in res["output"]


def test_list_files_with_pattern(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    list_files = REGISTRY["list_files"]

    (tmp_path / "test.py").write_text("a")
    (tmp_path / "test.txt").write_text("b")
    (tmp_path / "other.py").write_text("c")

    res = list_files({"path": str(tmp_path), "pattern": "*.py"})
    assert res["returncode"] == 0
    assert "test.py" in res["output"]
    assert "other.py" in res["output"]
    assert "test.txt" not in res["output"]


def test_list_files_recursive(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    list_files = REGISTRY["list_files"]

    (tmp_path / "root.txt").write_text("a")
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "nested.txt").write_text("b")

    res = list_files({"path": str(tmp_path), "pattern": "*.txt", "recursive": True})
    assert res["returncode"] == 0
    assert "root.txt" in res["output"]
    assert "nested.txt" in res["output"]


def test_list_files_not_directory(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    list_files = REGISTRY["list_files"]

    file_path = tmp_path / "file.txt"
    file_path.write_text("test")

    res = list_files({"path": str(file_path)})
    assert res["returncode"] == 20
    assert "Not a directory" in res["output"]


def test_list_files_nonexistent(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    list_files = REGISTRY["list_files"]

    res = list_files({"path": str(tmp_path / "nonexistent")})
    assert res["returncode"] == 2
    assert "not found" in res["output"].lower()


# ReadManyFiles Tests
def test_read_many_files_basic(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    read_many = REGISTRY["read_many_files"]

    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"
    file1.write_text("content1")
    file2.write_text("content2")

    res = read_many({"paths": [str(file1), str(file2)]})
    assert res["returncode"] == 0
    assert "content1" in res["output"]
    assert "content2" in res["output"]
    assert "START OF" in res["output"]
    assert "END OF" in res["output"]


def test_read_many_files_with_error(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    read_many = REGISTRY["read_many_files"]

    file1 = tmp_path / "exists.txt"
    file1.write_text("exists")
    missing = str(tmp_path / "missing.txt")

    res = read_many({"paths": [str(file1), missing]})
    assert res["returncode"] == 0
    assert "exists" in res["output"]
    assert "Error" in res["output"] or "not found" in res["output"].lower()


def test_read_many_files_missing_paths(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    read_many = REGISTRY["read_many_files"]

    res = read_many({"paths": []})
    assert res["returncode"] == 2
    assert "Missing 'paths'" in res["output"] or "not a list" in res["output"]


# AppendToFile Tests
def test_append_to_file_creates_file(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    append = REGISTRY["append_to_file"]

    file_path = tmp_path / "new.txt"

    res = append({"path": str(file_path), "content": "line1"})
    assert res["returncode"] == 0
    assert file_path.exists()
    assert "line1" in file_path.read_text()


def test_append_to_file_appends_content(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    append = REGISTRY["append_to_file"]

    file_path = tmp_path / "append.txt"
    file_path.write_text("existing\n")

    res = append({"path": str(file_path), "content": "new line"})
    assert res["returncode"] == 0

    content = file_path.read_text()
    assert "existing" in content
    assert "new line" in content


def test_append_to_file_creates_directories(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    append = REGISTRY["append_to_file"]

    nested = tmp_path / "sub1" / "sub2" / "file.txt"

    res = append({"path": str(nested), "content": "test"})
    assert res["returncode"] == 0
    assert nested.exists()


def test_append_to_file_missing_content(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    append = REGISTRY["append_to_file"]

    res = append({"path": str(tmp_path / "test.txt")})
    assert res["returncode"] == 2
    assert "Missing 'content'" in res["output"]


# InsertLines Tests
def test_insert_lines_at_beginning(tmp_path):
    """Test inserting lines at the beginning of a file"""
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    insert = REGISTRY["insert_lines"]

    test_file = tmp_path / "insert.txt"
    test_file.write_text("line1\nline2\nline3\n")

    res = insert({"path": str(test_file), "line_number": 1, "content": "# Header\n"})
    assert res["returncode"] == 0

    content = test_file.read_text()
    lines = content.splitlines()
    assert lines[0] == "# Header"
    assert lines[1] == "line1"
    assert lines[2] == "line2"


def test_insert_lines_in_middle(tmp_path):
    """Test inserting lines in the middle of a file"""
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    insert = REGISTRY["insert_lines"]

    test_file = tmp_path / "insert.txt"
    test_file.write_text("line1\nline2\nline3\n")

    res = insert({"path": str(test_file), "line_number": 2, "content": "inserted\n"})
    assert res["returncode"] == 0

    lines = test_file.read_text().splitlines()
    assert lines[0] == "line1"
    assert lines[1] == "inserted"
    assert lines[2] == "line2"
    assert lines[3] == "line3"


def test_insert_lines_at_end(tmp_path):
    """Test inserting lines at the end (beyond file length)"""
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    insert = REGISTRY["insert_lines"]

    test_file = tmp_path / "insert.txt"
    test_file.write_text("line1\nline2\n")

    # Insert at line 10 (beyond end of file)
    res = insert({"path": str(test_file), "line_number": 10, "content": "appended\n"})
    assert res["returncode"] == 0

    lines = test_file.read_text().splitlines()
    assert lines[-1] == "appended"


def test_insert_lines_multiline(tmp_path):
    """Test inserting multiple lines at once"""
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    insert = REGISTRY["insert_lines"]

    test_file = tmp_path / "insert.txt"
    test_file.write_text("line1\n")

    multi_content = "def func():\n    pass\n"
    res = insert({"path": str(test_file), "line_number": 2, "content": multi_content})
    assert res["returncode"] == 0
    assert "2 line(s)" in res["output"]

    content = test_file.read_text()
    assert "def func():" in content
    assert "    pass" in content


def test_insert_lines_with_imports(tmp_path):
    """Test realistic use case: adding imports at top of file"""
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    insert = REGISTRY["insert_lines"]

    test_file = tmp_path / "module.py"
    test_file.write_text("def main():\n    pass\n")

    imports = "import sys\nimport os\n\n"
    res = insert({"path": str(test_file), "line_number": 1, "content": imports})
    assert res["returncode"] == 0

    content = test_file.read_text()
    lines = content.splitlines()
    assert lines[0] == "import sys"
    assert lines[1] == "import os"
    assert lines[2] == ""
    assert lines[3] == "def main():"


def test_insert_lines_missing_path(tmp_path):
    """Test error handling for missing path"""
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    insert = REGISTRY["insert_lines"]

    res = insert({"path": "", "line_number": 1, "content": "test"})
    assert res["returncode"] == 2
    assert "Missing 'path'" in res["output"]


def test_insert_lines_missing_line_number(tmp_path):
    """Test error handling for missing line number"""
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    insert = REGISTRY["insert_lines"]

    test_file = tmp_path / "test.txt"
    test_file.write_text("test\n")

    res = insert({"path": str(test_file), "content": "test"})
    assert res["returncode"] == 2
    assert "Missing 'line_number'" in res["output"]


def test_insert_lines_invalid_line_number(tmp_path):
    """Test error handling for invalid line numbers"""
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    insert = REGISTRY["insert_lines"]

    test_file = tmp_path / "test.txt"
    test_file.write_text("test\n")

    # Test negative line number
    res = insert({"path": str(test_file), "line_number": 0, "content": "test"})
    assert res["returncode"] == 2
    assert "positive integer" in res["output"]

    # Test negative line number
    res = insert({"path": str(test_file), "line_number": -1, "content": "test"})
    assert res["returncode"] == 2


def test_insert_lines_nonexistent_file(tmp_path):
    """Test error handling for nonexistent file"""
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    insert = REGISTRY["insert_lines"]

    res = insert({"path": str(tmp_path / "nonexistent.txt"), "line_number": 1, "content": "test"})
    assert res["returncode"] == 2
    assert "not found" in res["output"].lower()


def test_insert_lines_automatic_newline(tmp_path):
    """Test that content without trailing newline gets one added"""
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    insert = REGISTRY["insert_lines"]

    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\n")

    # Content without trailing newline
    res = insert({"path": str(test_file), "line_number": 2, "content": "inserted"})
    assert res["returncode"] == 0

    # Should properly separate lines
    lines = test_file.read_text().splitlines()
    assert "line1" in lines
    assert "inserted" in lines


def test_insert_lines_preserves_existing_content(tmp_path):
    """Test that insertion doesn't modify existing lines"""
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    insert = REGISTRY["insert_lines"]

    test_file = tmp_path / "preserve.txt"
    original = "original line 1\noriginal line 2\noriginal line 3\n"
    test_file.write_text(original)

    res = insert({"path": str(test_file), "line_number": 2, "content": "NEW LINE\n"})
    assert res["returncode"] == 0

    content = test_file.read_text()
    # Original content should still be there
    assert "original line 1" in content
    assert "original line 2" in content
    assert "original line 3" in content
    assert "NEW LINE" in content

    # Check order
    lines = content.splitlines()
    assert lines[0] == "original line 1"
    assert lines[1] == "NEW LINE"
    assert lines[2] == "original line 2"
    assert lines[3] == "original line 3"


# CreateDirectory Tests
def test_create_directory_basic(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    create_dir = REGISTRY["create_directory"]

    new_dir = tmp_path / "newdir"
    res = create_dir({"path": str(new_dir)})
    assert res["returncode"] == 0
    assert new_dir.exists()
    assert new_dir.is_dir()


def test_create_directory_nested(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    create_dir = REGISTRY["create_directory"]

    nested = tmp_path / "a" / "b" / "c"
    res = create_dir({"path": str(nested)})
    assert res["returncode"] == 0
    assert nested.exists()
    assert nested.is_dir()


def test_create_directory_already_exists(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    create_dir = REGISTRY["create_directory"]

    existing = tmp_path / "existing"
    existing.mkdir()

    res = create_dir({"path": str(existing)})
    assert res["returncode"] == 0


def test_create_directory_missing_path(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    create_dir = REGISTRY["create_directory"]

    res = create_dir({"path": ""})
    assert res["returncode"] == 2
    assert "Missing 'path'" in res["output"]


# TodoList Tests
def test_todo_add_task(tmp_path):
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    todo = REGISTRY["todo"]

    res = todo({"action": "add", "task": "Test task"})
    assert res["returncode"] == 0
    assert "Added" in res["output"]


def test_todo_list_empty():
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    todo = REGISTRY["todo"]

    # Clear first
    todo({"action": "clear"})

    res = todo({"action": "list"})
    assert res["returncode"] == 0
    assert "No tasks" in res["output"]


def test_todo_list_tasks():
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    todo = REGISTRY["todo"]

    todo({"action": "clear"})
    todo({"action": "add", "task": "Task 1"})
    todo({"action": "add", "task": "Task 2"})

    res = todo({"action": "list"})
    assert res["returncode"] == 0
    assert "Task 1" in res["output"]
    assert "Task 2" in res["output"]
    assert "1." in res["output"]
    assert "2." in res["output"]


def test_todo_complete_task():
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    todo = REGISTRY["todo"]

    todo({"action": "clear"})
    todo({"action": "add", "task": "Complete me"})

    res = todo({"action": "complete", "index": 1})
    assert res["returncode"] == 0
    assert "Completed" in res["output"]

    res = todo({"action": "list"})
    assert "[x]" in res["output"]


def test_todo_complete_invalid_index():
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    todo = REGISTRY["todo"]

    todo({"action": "clear"})
    todo({"action": "add", "task": "Task"})

    res = todo({"action": "complete", "index": 99})
    assert res["returncode"] == 1
    assert "Invalid index" in res["output"]


def test_todo_complete_missing_index():
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    todo = REGISTRY["todo"]

    res = todo({"action": "complete"})
    assert res["returncode"] == 2
    assert "Missing 'index'" in res["output"]


def test_todo_clear():
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    todo = REGISTRY["todo"]

    todo({"action": "add", "task": "Task"})
    res = todo({"action": "clear"})
    assert res["returncode"] == 0

    res = todo({"action": "list"})
    assert "No tasks" in res["output"]


def test_todo_add_missing_task():
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    todo = REGISTRY["todo"]

    res = todo({"action": "add"})
    assert res["returncode"] == 2
    assert "Missing 'task'" in res["output"]


def test_todo_unknown_action():
    import minisweagent.tools.basic  # noqa: F401
    from minisweagent.tools import REGISTRY

    todo = REGISTRY["todo"]

    res = todo({"action": "invalid"})
    assert res["returncode"] == 1
    assert "Unknown action" in res["output"]
