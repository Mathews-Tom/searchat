"""Backup endpoints - create, list, restore, and delete backups."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from searchat.api.dependencies import (
    get_backup_manager,
    invalidate_search_index,
)


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/create")
async def create_backup(
    backup_name: str | None = None,
    snapshot: str | None = Query(None, description="Backup snapshot name (read-only)"),
):
    """Create a new backup of the index and data."""
    if snapshot is not None:
        raise HTTPException(status_code=403, detail="Backup operations are disabled in snapshot mode")
    try:
        backup_manager = get_backup_manager()
        logger.info(f"Creating backup: {backup_name or 'auto'}")
        metadata = backup_manager.create_backup(backup_name=backup_name)

        return {
            "success": True,
            "backup": metadata.to_dict(),
            "message": f"Backup created: {metadata.backup_path.name}"
        }

    except Exception as e:
        logger.error(f"Failed to create backup: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_backups():
    """List all available backups."""
    try:
        backup_manager = get_backup_manager()
        backups = backup_manager.list_backups()

        from searchat.services.backup import BackupManager

        enriched: list[dict] = []
        for b in backups:
            entry = b.to_dict()
            backup_path = str(entry.get("backup_path", ""))
            name = Path(backup_path).name if backup_path else ""

            if isinstance(backup_manager, BackupManager) and name:
                try:
                    entry.update(backup_manager.get_backup_summary(name))
                except Exception:
                    entry.update({
                        "name": name,
                        "backup_mode": "full",
                        "encrypted": False,
                        "parent_name": None,
                        "chain_length": 0,
                        "snapshot_browsable": False,
                        "has_manifest": False,
                    })
            else:
                # In tests backup_manager may be a mock; keep response stable.
                entry.update({
                    "name": name,
                    "backup_mode": "full",
                    "encrypted": False,
                    "parent_name": None,
                    "chain_length": 1 if name else 0,
                    "snapshot_browsable": False,
                    "has_manifest": False,
                })

            enriched.append(entry)

        return {
            "backups": enriched,
            "total": len(enriched),
            "backup_directory": str(backup_manager.backup_dir)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/restore")
async def restore_backup(
    backup_name: str,
    snapshot: str | None = Query(None, description="Backup snapshot name (read-only)"),
):
    """Restore from a backup."""
    if snapshot is not None:
        raise HTTPException(status_code=403, detail="Backup operations are disabled in snapshot mode")
    try:
        backup_manager = get_backup_manager()

        backup_path = backup_manager.backup_dir / backup_name

        if not backup_path.exists():
            raise HTTPException(status_code=404, detail=f"Backup not found: {backup_name}")

        logger.info(f"Restoring from backup: {backup_name}")

        pre_restore_metadata = backup_manager.restore_from_backup(
            backup_path=backup_path,
            create_pre_restore_backup=True
        )

        invalidate_search_index()

        result = {
            "success": True,
            "restored_from": backup_name,
            "message": f"Successfully restored from backup: {backup_name}"
        }

        if pre_restore_metadata:
            result["pre_restore_backup"] = pre_restore_metadata.to_dict()

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to restore backup: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/{backup_name}")
async def delete_backup(
    backup_name: str,
    snapshot: str | None = Query(None, description="Backup snapshot name (read-only)"),
):
    """Delete a backup."""
    if snapshot is not None:
        raise HTTPException(status_code=403, detail="Backup operations are disabled in snapshot mode")
    try:
        backup_manager = get_backup_manager()
        backup_path = backup_manager.backup_dir / backup_name

        if not backup_path.exists():
            raise HTTPException(status_code=404, detail=f"Backup not found: {backup_name}")

        logger.info(f"Deleting backup: {backup_name}")
        backup_manager.delete_backup(backup_path)

        return {
            "success": True,
            "deleted": backup_name,
            "message": f"Backup deleted: {backup_name}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete backup: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
