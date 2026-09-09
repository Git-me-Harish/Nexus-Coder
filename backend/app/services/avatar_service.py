"""
Profile avatar uploads.

Deliberately paranoid for its size, because this is the one route in the app
where a user hands us bytes that later get served back to other browsers:

  - The stored filename is ALWAYS generated here. The client's filename is
    never used, not even sanitized-and-reused, so there is no path to
    traverse out of the upload directory in the first place.
  - The type is decided by sniffing magic bytes, not by trusting the
    Content-Type header the client sent. That also means the extension we
    write (and therefore the Content-Type StaticFiles serves it back with)
    reflects what the file actually is.
  - Only raster formats are allowed. SVG is excluded on purpose: it is an
    XML document that can carry <script>, so serving one from the API origin
    would be a stored-XSS hole dressed up as a profile picture.
  - The size cap is enforced by reading cap+1 bytes and rejecting anything
    that fills it, rather than trusting Content-Length.
"""
from __future__ import annotations

import asyncio
import logging
import secrets
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.exceptions import api_error

logger = logging.getLogger("nexus.avatar")

URL_PATH_PREFIX = "/uploads/avatars"

# (extension, matcher) -- checked in order against the file's first bytes.
_SIGNATURES: list[tuple[str, callable]] = [
    ("png",  lambda b: b.startswith(b"\x89PNG\r\n\x1a\n")),
    ("jpg",  lambda b: b.startswith(b"\xff\xd8\xff")),
    ("gif",  lambda b: b.startswith(b"GIF87a") or b.startswith(b"GIF89a")),
    ("webp", lambda b: b.startswith(b"RIFF") and b[8:12] == b"WEBP"),
]


def avatar_dir() -> Path:
    path = Path(get_settings().upload_root).resolve() / "avatars"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sniff_extension(data: bytes) -> str | None:
    for ext, matches in _SIGNATURES:
        if matches(data):
            return ext
    return None


async def save_avatar(user_id: str, upload: UploadFile) -> str:
    """Writes the upload and returns the public URL to store on the user."""
    settings = get_settings()
    cap = settings.max_avatar_bytes

    data = await upload.read(cap + 1)
    if len(data) > cap:
        raise api_error(
            413, "AVATAR_TOO_LARGE",
            f"That image is larger than {cap // (1024 * 1024)} MB. Please pick a smaller one.",
        )
    if not data:
        raise api_error(400, "AVATAR_EMPTY", "That file is empty.")

    ext = _sniff_extension(data)
    if ext is None:
        raise api_error(
            415, "AVATAR_UNSUPPORTED_TYPE",
            "That doesn't look like a PNG, JPEG, GIF or WebP image.",
        )

    filename = f"{user_id}-{secrets.token_hex(8)}.{ext}"
    target = avatar_dir() / filename
    await asyncio.to_thread(target.write_bytes, data)

    return f"{settings.api_base_url.rstrip('/')}{URL_PATH_PREFIX}/{filename}"


async def delete_avatar_file(url: str | None) -> None:
    """
    Removes a previously uploaded file, ignoring anything we did not write.

    An avatar_url can also point at GitHub's CDN (copied over during GitHub
    sign-in), so "not ours" is the normal case, not an error -- and the
    basename check keeps a doctored URL from pointing this at another file.
    """
    if not url or URL_PATH_PREFIX not in url:
        return

    name = url.rsplit("/", 1)[-1]
    if not name or "/" in name or "\\" in name or name.startswith("."):
        return

    target = avatar_dir() / name
    try:
        resolved = target.resolve()
        if resolved.parent != avatar_dir().resolve():
            return
        await asyncio.to_thread(resolved.unlink, True)  # missing_ok=True
    except OSError:  # a stale file we cannot remove must not fail the request
        logger.warning("Could not delete old avatar file %s", name)
