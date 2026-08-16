"""FastAPI router for the Business Admin backend (issue #17). Mounted
alongside the WhatsApp webhook router in interfaces/whatsapp/app.py's
create_app() — one FastAPI service, two routers, per the settled design.

Every route resolves identity/scope through AdminInterfaceLayer.authorize()
before touching a repository or the config writer — this module translates
that layer's typed exceptions into HTTP responses and does the JSON
shuttling; it holds no authorization logic of its own.
"""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from adaptive_agent.admin.auth import create_access_token, verify_password
from adaptive_agent.admin.base import AdminRole, AdminStore
from adaptive_agent.admin.interface_layer import (
    AdminAuthError,
    AdminForbiddenError,
    AdminInterfaceLayer,
    InvalidConfirmationTokenError,
)
from adaptive_agent.business_config.loader import (
    BusinessConfigError,
    load_business_config,
)
from adaptive_agent.business_config.writer import (
    ConfigPatchError,
    update_business_config,
)
from adaptive_agent.menu.base import MenuItem
from adaptive_agent.menu.sqlite_repository import SqliteMenuRepository
from adaptive_agent.rooms.base import Room
from adaptive_agent.rooms.sqlite_repository import SqliteRoomRepository

_OWNER_ONLY = {AdminRole.OWNER}
_OWNER_AND_STAFF = {AdminRole.OWNER, AdminRole.STAFF}
_OWNER_AND_PLATFORM_OPERATOR = {AdminRole.OWNER, AdminRole.PLATFORM_OPERATOR}


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _bearer_token(authorization: str | None) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return authorization.removeprefix("Bearer ")


def _config_path(businesses_dir: Path, business_id: str) -> Path:
    path = businesses_dir / business_id / "business.yaml"
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Unknown business_id: {business_id!r}")
    return path


def build_admin_router(
    admin_interface_layer: AdminInterfaceLayer,
    admin_store: AdminStore,
    businesses_dir: Path,
    session_db_dir: Path,
) -> APIRouter:
    router = APIRouter(prefix="/admin/api/v1")

    # Lazily built, cached per business_id — one shared sqlite3 connection
    # per repository (house style: no connection pool, no per-request
    # connections), populated on first admin request rather than eagerly
    # for every Business at import time.
    _menu_repos: dict[str, SqliteMenuRepository] = {}
    _room_repos: dict[str, SqliteRoomRepository] = {}

    def _menu_repo(business_id: str) -> SqliteMenuRepository:
        if business_id not in _menu_repos:
            config = load_business_config(_config_path(businesses_dir, business_id))
            db_path = session_db_dir / f"{business_id}.sqlite3"
            kwargs: dict[str, Any] = {}
            if config.storage.table:
                kwargs["table"] = config.storage.table
            if config.storage.columns:
                kwargs["columns"] = config.storage.columns
            _menu_repos[business_id] = SqliteMenuRepository(db_path, **kwargs)
        return _menu_repos[business_id]

    def _room_repo(business_id: str) -> SqliteRoomRepository:
        if business_id not in _room_repos:
            config = load_business_config(_config_path(businesses_dir, business_id))
            db_path = session_db_dir / f"{business_id}.sqlite3"
            kwargs: dict[str, Any] = {}
            if config.storage.table:
                kwargs["table"] = config.storage.table
            if config.storage.columns:
                kwargs["columns"] = config.storage.columns
            _room_repos[business_id] = SqliteRoomRepository(db_path, **kwargs)
        return _room_repos[business_id]

    def _authorize(authorization: str | None, business_id: str | None, allowed_roles: set[AdminRole]):
        token = _bearer_token(authorization)
        try:
            return admin_interface_layer.authorize(token, business_id, allowed_roles)
        except AdminAuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AdminForbiddenError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @router.post("/auth/login", response_model=LoginResponse)
    def login(body: LoginRequest) -> LoginResponse:
        user = admin_store.get_user_by_email(body.email)
        if user is None or not verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        return LoginResponse(access_token=create_access_token(user))

    @router.get("/businesses/{business_id}/config")
    def get_config(business_id: str, authorization: str | None = Header(default=None)) -> dict:
        _authorize(authorization, business_id, _OWNER_ONLY)
        try:
            config = load_business_config(_config_path(businesses_dir, business_id))
        except BusinessConfigError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return config.model_dump(mode="json")

    @router.patch("/businesses/{business_id}/config")
    def patch_config(
        business_id: str, patch: dict[str, Any], authorization: str | None = Header(default=None)
    ) -> dict:
        user = _authorize(authorization, business_id, _OWNER_ONLY)
        path = _config_path(businesses_dir, business_id)
        before = load_business_config(path).model_dump(mode="json")
        try:
            updated = update_business_config(path, patch)
        except ConfigPatchError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        after = updated.model_dump(mode="json")
        admin_interface_layer.record_audit(
            user, business_id, "config.update", before=str(before), after=str(after)
        )
        return after

    # --- Menu items -------------------------------------------------

    @router.get("/businesses/{business_id}/menu-items")
    def list_menu_items(
        business_id: str, authorization: str | None = Header(default=None)
    ) -> list[MenuItem]:
        _authorize(authorization, business_id, _OWNER_AND_STAFF)
        return _menu_repo(business_id).list_items()

    @router.post("/businesses/{business_id}/menu-items", status_code=201)
    def create_menu_item(
        business_id: str, item: MenuItem, authorization: str | None = Header(default=None)
    ) -> MenuItem:
        user = _authorize(authorization, business_id, _OWNER_AND_STAFF)
        repo = _menu_repo(business_id)
        if repo.get_item(item.name) is not None:
            raise HTTPException(status_code=409, detail=f"Menu item already exists: {item.name!r}")
        repo.seed([item])
        admin_interface_layer.record_audit(
            user, business_id, "menu_item.create", after=item.model_dump_json()
        )
        return item

    @router.patch("/businesses/{business_id}/menu-items/{name}")
    def update_menu_item(
        business_id: str,
        name: str,
        patch: dict[str, Any],
        authorization: str | None = Header(default=None),
    ) -> MenuItem:
        user = _authorize(authorization, business_id, _OWNER_AND_STAFF)
        repo = _menu_repo(business_id)
        existing = repo.get_item(name)
        if existing is None:
            raise HTTPException(status_code=404, detail=f"No such menu item: {name!r}")
        updated = existing.model_copy(update=patch)
        repo.seed([updated])
        admin_interface_layer.record_audit(
            user,
            business_id,
            "menu_item.update",
            before=existing.model_dump_json(),
            after=updated.model_dump_json(),
        )
        return updated

    @router.delete("/businesses/{business_id}/menu-items/{name}")
    def delete_menu_item(
        business_id: str,
        name: str,
        confirm_token: str | None = None,
        authorization: str | None = Header(default=None),
    ) -> dict:
        user = _authorize(authorization, business_id, _OWNER_AND_STAFF)
        repo = _menu_repo(business_id)
        existing = repo.get_item(name)
        if existing is None:
            raise HTTPException(status_code=404, detail=f"No such menu item: {name!r}")

        description = f"Delete menu item {name!r} from {business_id}"
        if confirm_token is None:
            token = admin_interface_layer.request_confirmation(description)
            return {"status": "confirmation_required", "confirm_token": token, "description": description}
        try:
            admin_interface_layer.resolve_confirmation(confirm_token)
        except InvalidConfirmationTokenError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        repo.delete_item(name)
        admin_interface_layer.record_audit(
            user, business_id, "menu_item.delete", before=existing.model_dump_json()
        )
        return {"status": "deleted"}

    # --- Rooms --------------------------------------------------------

    @router.get("/businesses/{business_id}/rooms")
    def list_rooms(business_id: str, authorization: str | None = Header(default=None)) -> list[Room]:
        _authorize(authorization, business_id, _OWNER_AND_STAFF)
        return _room_repo(business_id).list_rooms()

    @router.post("/businesses/{business_id}/rooms", status_code=201)
    def create_room(
        business_id: str, room: Room, authorization: str | None = Header(default=None)
    ) -> Room:
        user = _authorize(authorization, business_id, _OWNER_AND_STAFF)
        repo = _room_repo(business_id)
        if repo.get_room(room.name) is not None:
            raise HTTPException(status_code=409, detail=f"Room already exists: {room.name!r}")
        repo.seed([room])
        admin_interface_layer.record_audit(
            user, business_id, "room.create", after=room.model_dump_json()
        )
        return room

    @router.patch("/businesses/{business_id}/rooms/{name}")
    def update_room(
        business_id: str,
        name: str,
        patch: dict[str, Any],
        authorization: str | None = Header(default=None),
    ) -> Room:
        user = _authorize(authorization, business_id, _OWNER_AND_STAFF)
        repo = _room_repo(business_id)
        existing = repo.get_room(name)
        if existing is None:
            raise HTTPException(status_code=404, detail=f"No such room: {name!r}")
        updated = existing.model_copy(update=patch)
        repo.seed([updated])
        admin_interface_layer.record_audit(
            user, business_id, "room.update", before=existing.model_dump_json(), after=updated.model_dump_json()
        )
        return updated

    @router.delete("/businesses/{business_id}/rooms/{name}")
    def delete_room(
        business_id: str,
        name: str,
        confirm_token: str | None = None,
        authorization: str | None = Header(default=None),
    ) -> dict:
        user = _authorize(authorization, business_id, _OWNER_AND_STAFF)
        repo = _room_repo(business_id)
        existing = repo.get_room(name)
        if existing is None:
            raise HTTPException(status_code=404, detail=f"No such room: {name!r}")

        description = f"Delete room {name!r} from {business_id}"
        if confirm_token is None:
            token = admin_interface_layer.request_confirmation(description)
            return {"status": "confirmation_required", "confirm_token": token, "description": description}
        try:
            admin_interface_layer.resolve_confirmation(confirm_token)
        except InvalidConfirmationTokenError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        repo.delete_room(name)
        admin_interface_layer.record_audit(
            user, business_id, "room.delete", before=existing.model_dump_json()
        )
        return {"status": "deleted"}

    # --- Audit log ------------------------------------------------------

    @router.get("/businesses/{business_id}/audit-log")
    def get_audit_log(
        business_id: str, authorization: str | None = Header(default=None)
    ) -> list[dict]:
        _authorize(authorization, business_id, _OWNER_AND_PLATFORM_OPERATOR)
        entries = admin_store.list_audit_log(business_id)
        return [entry.model_dump(mode="json") for entry in entries]

    return router
