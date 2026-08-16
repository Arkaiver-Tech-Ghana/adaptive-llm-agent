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
)
from adaptive_agent.business_config.loader import (
    BusinessConfigError,
    load_business_config,
)
from adaptive_agent.business_config.provisioning import (
    BusinessAlreadyExistsError,
    InvalidBusinessIdError,
    OwnerEmailAlreadyExistsError,
    provision_business,
)
from adaptive_agent.business_config.writer import (
    ConfigPatchError,
    update_business_config,
)

_OWNER_ONLY = {AdminRole.OWNER}
_OWNER_AND_PLATFORM_OPERATOR = {AdminRole.OWNER, AdminRole.PLATFORM_OPERATOR}


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SignupRequest(BaseModel):
    business_id: str
    display_name: str
    owner_email: str
    owner_password: str


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
) -> APIRouter:
    router = APIRouter(prefix="/admin/api/v1")

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

    @router.post("/auth/signup", response_model=LoginResponse, status_code=201)
    def signup(body: SignupRequest) -> LoginResponse:
        try:
            owner = provision_business(
                business_id=body.business_id,
                display_name=body.display_name,
                owner_email=body.owner_email,
                owner_password=body.owner_password,
                businesses_dir=businesses_dir,
                admin_store=admin_store,
            )
        except InvalidBusinessIdError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (BusinessAlreadyExistsError, OwnerEmailAlreadyExistsError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        admin_interface_layer.record_audit(
            owner, body.business_id, "business.signup", after=owner.email
        )
        return LoginResponse(access_token=create_access_token(owner))

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

    # --- Audit log ------------------------------------------------------

    @router.get("/businesses/{business_id}/audit-log")
    def get_audit_log(
        business_id: str, authorization: str | None = Header(default=None)
    ) -> list[dict]:
        _authorize(authorization, business_id, _OWNER_AND_PLATFORM_OPERATOR)
        entries = admin_store.list_audit_log(business_id)
        return [entry.model_dump(mode="json") for entry in entries]

    return router
