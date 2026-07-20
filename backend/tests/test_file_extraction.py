from app.agents.file_extraction import extract_files_from_output


def test_extracts_single_file_block():
    text = 'Here is the file:\n```python\n// main.py\nprint("hello")\n```\nDone.'
    files = extract_files_from_output(text)
    assert len(files) == 1
    assert files[0].path == "main.py"
    assert files[0].language == "python"
    assert 'print("hello")' in files[0].content


def test_extracts_multiple_file_blocks():
    text = (
        '```ts\n// src/index.ts\nconsole.log(1);\n```\n'
        'and also\n'
        '```py\n// app/main.py\nprint(2)\n```\n'
    )
    files = extract_files_from_output(text)
    assert len(files) == 2
    assert {f.path for f in files} == {"src/index.ts", "app/main.py"}


def test_language_inferred_from_extension_not_fence_tag():
    # LANG_MAP keys off the file extension, not the fence's language tag --
    # matches the original TS extractFilesFromOutput exactly.
    text = '```text\n// script.py\nprint(1)\n```'
    files = extract_files_from_output(text)
    assert files[0].language == "python"


def test_ignores_code_blocks_without_a_path_comment():
    text = '```js\nconsole.log("no path comment, should be ignored");\n```'
    assert extract_files_from_output(text) == []


def test_no_file_blocks_returns_empty_list():
    assert extract_files_from_output("Just a plain text response, no code.") == []