"""Where uploaded files live. Local disk for now; an S3-compatible backend can replace it later.

Storage keys are server-generated UUIDs. User-supplied filenames never touch the filesystem,
which rules out path traversal ("../../etc/passwd") by construction.
"""

import os
import re
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends

from app.config import get_settings

_KEY_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._tmp = self.root / ".tmp"
        self._tmp.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def new_key() -> str:
        return str(uuid.uuid4())

    def path_for(self, key: str) -> Path:
        if not _KEY_PATTERN.fullmatch(key):
            raise ValueError("invalid storage key")
        return self.root / key

    def new_temp_path(self) -> Path:
        return self._tmp / str(uuid.uuid4())

    def commit_temp(self, temp_path: Path, key: str) -> None:
        os.replace(temp_path, self.path_for(key))  # atomic on the same filesystem

    def delete(self, key: str) -> None:
        self.path_for(key).unlink(missing_ok=True)


@lru_cache
def get_storage() -> LocalStorage:
    return LocalStorage(get_settings().upload_dir)


StorageDep = Annotated[LocalStorage, Depends(get_storage)]
