from __future__ import annotations

from pathlib import Path
from typing import Optional

import aiofiles


class FileService:
    def __init__(self, base_dir: str | Path = "data/uploads") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def save_bytes(self, content: bytes, filename: str) -> Path:
        target = self.base_dir / filename
        async with aiofiles.open(target, "wb") as f:
            await f.write(content)
        return target

    async def read_bytes(self, filename: str) -> Optional[bytes]:
        target = self.base_dir / filename
        if not target.exists():
            return None
        async with aiofiles.open(target, "rb") as f:
            return await f.read()
