"""FastAPI router for the generic entity/table system (ADR 0008) — lets a
Business owner define their own tables/columns and fill in their own data,
instead of a developer adding a new repository class + Admin CRUD routes
per Business (the old ``rooms``/``menu-items`` pattern this replaces).

Split out from interfaces/admin/router.py, which was already large before
this addition; reuses that module's ``_bearer_token``/``_config_path`` —
pure helpers, not closures — instead of duplicating them. Same
authorize-before-touching-a-repository shape as the rest of the Admin
backend: every route resolves scope through AdminInterfaceLayer.authorize()
before this module does anything else.
"""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from adaptive_agent.admin.base import AdminRole, AdminStore
from adaptive_agent.admin.interface_layer import (
    AdminAuthError,
    AdminForbiddenError,
    AdminInterfaceLayer,
    InvalidConfirmationTokenError,
)
from adaptive_agent.entities.base import ColumnDef, TableDef
from adaptive_agent.entities.sqlite_repository import (
    ColumnAlreadyExistsError,
    InvalidTableConfigError,
    InvalidToolLinkedTableError,
    SqliteEntityRepository,
    TableAlreadyExistsError,
    UnknownColumnError,
    UnknownTableError,
)
from adaptive_agent.interfaces.admin.router import _bearer_token, _config_path


class RenameColumnRequest(BaseModel):
    name: str

_OWNER_ONLY = {AdminRole.OWNER}


def build_entities_router(
    admin_interface_layer: AdminInterfaceLayer,
    admin_store: AdminStore,
    businesses_dir: Path,
    session_db_dir: Path,
) -> APIRouter:
    router = APIRouter(prefix="/admin/api/v1")

    # Lazily built, cached per business_id — one shared sqlite3 connection
    # per Business (house style: no connection pool, no per-request
    # connections), same convention the old _menu_repo/_room_repo caches
    # used.
    _entity_repos: dict[str, SqliteEntityRepository] = {}

    def _entity_repo(business_id: str) -> SqliteEntityRepository:
        if business_id not in _entity_repos:
            _config_path(businesses_dir, business_id)  # 404s on unknown business_id
            db_path = session_db_dir / f"{business_id}.sqlite3"
            _entity_repos[business_id] = SqliteEntityRepository(db_path)
        return _entity_repos[business_id]

    def _authorize(authorization: str | None, business_id: str | None, allowed_roles: set[AdminRole]):
        token = _bearer_token(authorization)
        try:
            return admin_interface_layer.authorize(token, business_id, allowed_roles)
        except AdminAuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AdminForbiddenError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    def _require_table(repo: SqliteEntityRepository, table_name: str) -> TableDef:
        for table in repo.list_tables():
            if table.table_name == table_name:
                return table
        raise HTTPException(status_code=404, detail=f"No such table: {table_name!r}")

    # --- Tables -----------------------------------------------------

    @router.get("/businesses/{business_id}/tables")
    def list_tables(
        business_id: str, authorization: str | None = Header(default=None)
    ) -> list[TableDef]:
        _authorize(authorization, business_id, _OWNER_ONLY)
        return _entity_repo(business_id).list_tables()

    @router.post("/businesses/{business_id}/tables", status_code=201)
    def create_table(
        business_id: str, table_def: TableDef, authorization: str | None = Header(default=None)
    ) -> TableDef:
        user = _authorize(authorization, business_id, _OWNER_ONLY)
        try:
            _entity_repo(business_id).create_table(table_def)
        except TableAlreadyExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (InvalidTableConfigError, InvalidToolLinkedTableError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        admin_interface_layer.record_audit(
            user, business_id, "table.create", after=table_def.model_dump_json()
        )
        return table_def

    @router.delete("/businesses/{business_id}/tables/{table_name}")
    def delete_table(
        business_id: str,
        table_name: str,
        confirm_token: str | None = None,
        authorization: str | None = Header(default=None),
    ) -> dict:
        user = _authorize(authorization, business_id, _OWNER_ONLY)
        repo = _entity_repo(business_id)
        existing = _require_table(repo, table_name)

        description = f"Delete table {table_name!r} from {business_id}"
        if confirm_token is None:
            token = admin_interface_layer.request_confirmation(description)
            return {"status": "confirmation_required", "confirm_token": token, "description": description}
        try:
            admin_interface_layer.resolve_confirmation(confirm_token)
        except InvalidConfirmationTokenError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        repo.drop_table(table_name)
        admin_interface_layer.record_audit(
            user, business_id, "table.delete", before=existing.model_dump_json()
        )
        return {"status": "deleted"}

    # --- Columns --------------------------------------------------------
    # Add/rename are immediate (non-destructive); drop reuses the same
    # Confirmation Request pattern as delete_table/delete_row below since
    # it discards every row's value for that column.

    @router.post("/businesses/{business_id}/tables/{table_name}/columns", status_code=201)
    def add_column(
        business_id: str,
        table_name: str,
        column: ColumnDef,
        authorization: str | None = Header(default=None),
    ) -> TableDef:
        user = _authorize(authorization, business_id, _OWNER_ONLY)
        repo = _entity_repo(business_id)
        before = _require_table(repo, table_name)
        try:
            updated = repo.add_column(table_name, column)
        except ColumnAlreadyExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except InvalidTableConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        admin_interface_layer.record_audit(
            user, business_id, "table.column.add", before=before.model_dump_json(), after=updated.model_dump_json()
        )
        return updated

    @router.patch("/businesses/{business_id}/tables/{table_name}/columns/{column_name}")
    def rename_column(
        business_id: str,
        table_name: str,
        column_name: str,
        body: RenameColumnRequest,
        authorization: str | None = Header(default=None),
    ) -> TableDef:
        user = _authorize(authorization, business_id, _OWNER_ONLY)
        repo = _entity_repo(business_id)
        before = _require_table(repo, table_name)
        try:
            updated = repo.rename_column(table_name, column_name, body.name)
        except UnknownColumnError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (ColumnAlreadyExistsError, InvalidTableConfigError, InvalidToolLinkedTableError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        admin_interface_layer.record_audit(
            user, business_id, "table.column.rename", before=before.model_dump_json(), after=updated.model_dump_json()
        )
        return updated

    @router.delete("/businesses/{business_id}/tables/{table_name}/columns/{column_name}")
    def delete_column(
        business_id: str,
        table_name: str,
        column_name: str,
        confirm_token: str | None = None,
        authorization: str | None = Header(default=None),
    ) -> dict:
        user = _authorize(authorization, business_id, _OWNER_ONLY)
        repo = _entity_repo(business_id)
        before = _require_table(repo, table_name)
        if not any(c.name == column_name for c in before.columns):
            raise HTTPException(status_code=404, detail=f"No such column: {column_name!r}")

        description = f"Delete column {column_name!r} from {business_id}/{table_name}"
        if confirm_token is None:
            token = admin_interface_layer.request_confirmation(description)
            return {"status": "confirmation_required", "confirm_token": token, "description": description}
        try:
            admin_interface_layer.resolve_confirmation(confirm_token)
        except InvalidConfirmationTokenError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        try:
            updated = repo.drop_column(table_name, column_name)
        except InvalidToolLinkedTableError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        admin_interface_layer.record_audit(
            user, business_id, "table.column.delete", before=before.model_dump_json(), after=updated.model_dump_json()
        )
        return {"status": "deleted"}

    # --- Rows ---------------------------------------------------------

    @router.get("/businesses/{business_id}/tables/{table_name}/rows")
    def list_rows(
        business_id: str, table_name: str, authorization: str | None = Header(default=None)
    ) -> list[dict]:
        _authorize(authorization, business_id, _OWNER_ONLY)
        repo = _entity_repo(business_id)
        _require_table(repo, table_name)
        try:
            return repo.list_rows(table_name)
        except UnknownTableError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/businesses/{business_id}/tables/{table_name}/rows", status_code=201)
    def create_row(
        business_id: str,
        table_name: str,
        row: dict[str, Any],
        authorization: str | None = Header(default=None),
    ) -> dict:
        user = _authorize(authorization, business_id, _OWNER_ONLY)
        repo = _entity_repo(business_id)
        _require_table(repo, table_name)
        row = {k: v for k, v in row.items() if k != "id"}  # POST always creates a new row
        stored = repo.upsert_row(table_name, row)
        admin_interface_layer.record_audit(
            user, business_id, "row.create", after=str(stored)
        )
        return stored

    @router.patch("/businesses/{business_id}/tables/{table_name}/rows/{row_id}")
    def update_row(
        business_id: str,
        table_name: str,
        row_id: str,
        patch: dict[str, Any],
        authorization: str | None = Header(default=None),
    ) -> dict:
        user = _authorize(authorization, business_id, _OWNER_ONLY)
        repo = _entity_repo(business_id)
        _require_table(repo, table_name)
        existing = repo.get_row(table_name, row_id)
        if existing is None:
            raise HTTPException(status_code=404, detail=f"No such row: {row_id!r}")
        updated = repo.upsert_row(table_name, {**existing, **patch, "id": row_id})
        admin_interface_layer.record_audit(
            user, business_id, "row.update", before=str(existing), after=str(updated)
        )
        return updated

    @router.delete("/businesses/{business_id}/tables/{table_name}/rows/{row_id}")
    def delete_row(
        business_id: str,
        table_name: str,
        row_id: str,
        confirm_token: str | None = None,
        authorization: str | None = Header(default=None),
    ) -> dict:
        user = _authorize(authorization, business_id, _OWNER_ONLY)
        repo = _entity_repo(business_id)
        _require_table(repo, table_name)
        existing = repo.get_row(table_name, row_id)
        if existing is None:
            raise HTTPException(status_code=404, detail=f"No such row: {row_id!r}")

        description = f"Delete row {row_id!r} from {business_id}/{table_name}"
        if confirm_token is None:
            token = admin_interface_layer.request_confirmation(description)
            return {"status": "confirmation_required", "confirm_token": token, "description": description}
        try:
            admin_interface_layer.resolve_confirmation(confirm_token)
        except InvalidConfirmationTokenError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        repo.delete_row(table_name, row_id)
        admin_interface_layer.record_audit(
            user, business_id, "row.delete", before=str(existing)
        )
        return {"status": "deleted"}

    return router
