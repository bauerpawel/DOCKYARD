"""Publish a staged build, restoring all previous outputs if a rename fails."""
import os
from pathlib import Path
import shutil


class PublishError(RuntimeError):
    def __init__(self, message: str, *, preserve_stage: bool = False):
        super().__init__(message)
        self.preserve_stage = preserve_stage


def publish_outputs(root: Path, stage: Path) -> None:
    names = ("templates.json", "docs", "repository.json")
    backup = stage / "backup"
    backup.mkdir()
    for name in names:
        target = root / name
        if target.is_symlink() or (target.exists() and target.is_dir() != (name == "docs")):
            raise PublishError(f"refusing to replace unexpected output: {target}")
    moved = []
    installed = []
    try:
        for name in names:
            if (root / name).exists():
                os.replace(root / name, backup / name)
                moved.append(name)
            os.replace(stage / name, root / name)
            installed.append(name)
    except OSError as error:
        try:
            for name in reversed(installed):
                target = root / name
                # These three fixed targets are direct children of the repository.
                if target.parent.resolve() != root.resolve() or target.is_symlink():
                    raise OSError(f"unsafe rollback target: {target}")
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            for name in reversed(moved):
                os.replace(backup / name, root / name)
        except OSError as rollback_error:
            raise PublishError(f"publication failed ({error}); rollback failed ({rollback_error}); backups retained in {stage}", preserve_stage=True) from error
        raise PublishError(f"publication failed; previous outputs restored: {error}") from error
