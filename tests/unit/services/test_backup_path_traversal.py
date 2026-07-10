"""Regression tests for the backup-name path traversal fix.

`BackupManager` and `api/routers/backup.py` used to join a caller-supplied
`backup_name` (from `DELETE /api/backup/delete/{backup_name}`,
`POST /api/backup/restore`, `GET /api/backup/validate/{backup_name}`,
`GET /api/backup/chain/{backup_name}`, and the `backup_name`/`parent`
custom-name prefixes on `POST /api/backup/create` and
`POST /api/backup/incremental/create`) directly onto `backup_dir` with no
containment check: `backup_manager.backup_dir / backup_name`. A name of
`".."` resolves to `backup_dir`'s parent -- the live `~/.searchat` data
directory itself -- turning the unauthenticated DELETE endpoint into a
`shutil.rmtree(~/.searchat)` primitive, and letting the CREATE endpoints
write a backup's contents to an attacker-chosen filesystem location
outside `backup_dir` entirely.

`resolve_backup_path` / `_validate_backup_name_component` close this by
rejecting empty names, `.`/`..`, embedded path separators, and (as a
second, independent check) any resolved path that still lands outside
`backup_dir`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from searchat.services.backup import BackupManager


@pytest.mark.unit
class TestResolveBackupPathRejectsTraversal:
    """Direct tests of the validation helper itself."""

    @pytest.mark.parametrize(
        "name",
        [
            "..",
            ".",
            "",
            "../sibling",
            "sub/dir",
            "sub\\dir",
            "..\\..\\evil",
            "C:",
            "c:",
            "D:",
            "name:stream",
        ],
    )
    def test_rejects_unsafe_names(self, temp_search_dir: Path, name: str) -> None:
        mgr = BackupManager(temp_search_dir)
        with pytest.raises(ValueError):
            mgr.resolve_backup_path(name)

    def test_accepts_a_real_backup_name(self, temp_search_dir: Path) -> None:
        mgr = BackupManager(temp_search_dir)
        meta = mgr.create_backup(backup_name="ok")
        name = meta.backup_path.name

        resolved = mgr.resolve_backup_path(name)

        assert resolved == meta.backup_path.resolve()
        assert resolved.is_relative_to(mgr.backup_dir.resolve())

    def test_dotdot_would_have_escaped_to_backup_dirs_parent(
        self, temp_search_dir: Path
    ) -> None:
        """Prove exactly what `backup_name=".."` used to resolve to.

        This is the live `~/.searchat` data directory in production; here
        it is `temp_search_dir`, the parent of `backup_dir`.
        """
        mgr = BackupManager(temp_search_dir)
        unsafe_join = mgr.backup_dir / ".."

        assert unsafe_join.resolve() == mgr.backup_dir.parent.resolve()
        assert unsafe_join.resolve() == temp_search_dir.resolve()


@pytest.mark.unit
class TestServiceEntryPointsRejectTraversal:
    """Every public BackupManager method that used to join backup_dir
    directly from a caller-supplied name must now refuse `".."`."""

    def test_resolve_backup_chain_rejects_dotdot(self, temp_search_dir: Path) -> None:
        mgr = BackupManager(temp_search_dir)
        with pytest.raises(ValueError):
            mgr.resolve_backup_chain("..")

    def test_validate_backup_artifact_rejects_dotdot(self, temp_search_dir: Path) -> None:
        mgr = BackupManager(temp_search_dir)
        result = mgr.validate_backup_artifact("..")
        assert result["valid"] is False

    def test_get_backup_summary_rejects_dotdot(self, temp_search_dir: Path) -> None:
        mgr = BackupManager(temp_search_dir)
        result = mgr.get_backup_summary("..")
        assert result["valid"] is False

    def test_set_pinned_rejects_dotdot(self, temp_search_dir: Path) -> None:
        mgr = BackupManager(temp_search_dir)
        with pytest.raises(FileNotFoundError):
            mgr.set_pinned("..", True)

    def test_materialize_backup_rejects_dotdot(self, temp_search_dir: Path, tmp_path: Path) -> None:
        mgr = BackupManager(temp_search_dir)
        with pytest.raises(ValueError):
            mgr.materialize_backup(backup_name="..", dest_dir=tmp_path / "out")


@pytest.mark.unit
class TestCreateBackupRejectsWriteTraversal:
    """The custom `backup_name` prefix accepted by create_backup /
    create_incremental_backup is a WRITE-side join: a malicious value
    would write the backup's contents outside `backup_dir` entirely,
    not just read from it."""

    def test_create_backup_rejects_traversal_name_and_writes_nothing_outside(
        self, temp_search_dir: Path, tmp_path: Path
    ) -> None:
        mgr = BackupManager(temp_search_dir)
        escape_target = tmp_path / "outside"

        with pytest.raises(ValueError):
            mgr.create_backup(backup_name=f"../../../../../..{escape_target}")

        assert not escape_target.exists()
        # Nothing was created inside backup_dir either.
        assert list(mgr.backup_dir.iterdir()) == []

    def test_create_incremental_backup_rejects_traversal_custom_name(
        self, temp_search_dir: Path
    ) -> None:
        mgr = BackupManager(temp_search_dir)
        base_meta = mgr.create_backup(backup_name="base")

        with pytest.raises(ValueError):
            mgr.create_incremental_backup(
                parent_name=base_meta.backup_path.name,
                backup_name="../evil",
            )

    def test_create_incremental_backup_rejects_traversal_parent_name(
        self, temp_search_dir: Path
    ) -> None:
        mgr = BackupManager(temp_search_dir)
        with pytest.raises(ValueError):
            mgr.create_incremental_backup(parent_name="..")


@pytest.mark.unit
class TestDeleteEndpointRejectsEncodedTraversal:
    """`backup_name="..".` reaches the DELETE route via `%2e%2e` -- httpx's
    own URL normalization collapses a literal unencoded `..` segment
    before the request is even sent, but percent-encoded dots are not
    normalized client-side and decode to `..` once routed. A live
    pre-fix reproduction against a real BackupManager confirmed this
    percent-encoded request actually executed
    `shutil.rmtree(backup_dir.parent)`, deleting a sentinel file placed
    directly in the data directory one level above `backup_dir`.
    """

    def test_delete_encoded_dotdot_does_not_touch_parent_directory(
        self, temp_search_dir: Path
    ) -> None:
        from unittest.mock import patch

        from fastapi.testclient import TestClient

        from searchat.api.app import app

        sentinel = temp_search_dir / "sentinel.txt"
        sentinel.write_text("do not delete me")
        mgr = BackupManager(temp_search_dir)

        client = TestClient(app)
        with patch("searchat.api.routers.backup.get_backup_manager", return_value=mgr):
            response = client.request("DELETE", "/api/backup/delete/%2e%2e")

        assert response.status_code == 404
        assert sentinel.exists()
        assert temp_search_dir.exists()

