"""
Extracts file blocks from agent output and persists them as SessionFile
rows -- this was entirely missing from the initial migration. The original
TS backend's `extractFilesFromOutput` (src/lib/nexus/prompts.ts) parsed
fenced code blocks with a leading `// path/to/file.ext` comment and wrote
them to the DB on every agent turn; the Python migration ported the chat
and phase-orchestration path but dropped this, so `SessionFile` rows were
never created and the Files panel in the UI was permanently empty.

Kept as a regex-based extractor matching the original exactly (same
capture groups, same LANG_MAP) rather than something fancier, so behavior
is a drop-in match for what the frontend already expects.
"""
import re
from dataclasses import dataclass

_FILE_BLOCK_RE = re.compile(r"```(\w+)?\s*\n//\s*(.+?)\s*\n([\s\S]*?)```")

LANG_MAP: dict[str, str] = {
    "ts": "typescript", "tsx": "typescript", "js": "javascript", "jsx": "javascript",
    "py": "python", "rb": "ruby", "go": "go", "rs": "rust", "java": "java", "kt": "kotlin",
    "swift": "swift", "php": "php", "cs": "csharp", "cpp": "cpp", "c": "c", "h": "c",
    "sql": "sql", "sh": "bash", "yml": "yaml", "yaml": "yaml", "json": "json",
    "html": "html", "css": "css", "scss": "scss", "md": "markdown",
    "toml": "toml", "ini": "ini", "env": "bash", "dockerfile": "dockerfile",
}


@dataclass
class ExtractedFile:
    path: str
    language: str
    content: str


def extract_files_from_output(text: str) -> list[ExtractedFile]:
    files: list[ExtractedFile] = []
    for match in _FILE_BLOCK_RE.finditer(text):
        fence_lang, path, content = match.group(1), match.group(2).strip(), match.group(3)
        if not path or not content:
            continue
        ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        language = LANG_MAP.get(ext, fence_lang or "text")
        files.append(ExtractedFile(path=path, language=language, content=content))
    return files