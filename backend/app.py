"""FastAPI server: browser does speech-to-text and text-to-speech; the server turns
transcript segments into a checked form."""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .dialog import SESSION_TTL_SECONDS, Session, SessionStore
from .extractor import make_extractor
from .schema import list_schemas, load_schema

WEB = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="Bol Ke Bharo")
store = SessionStore()
extractor = make_extractor()


# Signed snapshots let a conversation continue on any server instance (serverless hosting runs several).
# Set BKB_SECRET to the same value on every instance; without it each process signs with its own key.
SECRET = (os.environ.get("BKB_SECRET") or secrets.token_hex(32)).encode()


def _sign(s: Session) -> str:
    body = base64.urlsafe_b64encode(json.dumps(s.to_dict(), ensure_ascii=False).encode()).decode()
    mac = hmac.new(SECRET, body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{mac}"


def _restore(sid: str, snapshot: str | None) -> Session | None:
    """Rebuild a session from a snapshot this server signed. Rejects forged, mismatched or expired ones."""
    try:
        body, mac = (snapshot or "").rsplit(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(mac, hmac.new(SECRET, body.encode(), hashlib.sha256).hexdigest()):
        return None
    d = json.loads(base64.urlsafe_b64decode(body))
    if d["id"] != sid or time.time() - d["touched"] > SESSION_TTL_SECONDS:
        return None
    return store.put(Session.from_dict(d, load_schema(d["form_id"])))


def _state(s: Session) -> dict:
    return s.public_state() | {"snapshot": _sign(s)}


class NewSession(BaseModel):
    form_id: str = "pension_up"
    lang: str = "hi"


class Turn(BaseModel):
    speaker: str  # "operator" | "citizen"
    text: str
    snapshot: str | None = None


class Edit(BaseModel):
    key: str
    value: str
    snapshot: str | None = None


class Snap(BaseModel):
    snapshot: str | None = None


def _session(sid, snapshot: str | None = None):
    try:
        return store.get(sid)
    except KeyError:
        s = _restore(sid, snapshot)
        if s is None:
            raise HTTPException(404, "session expired or not found")
        return s


@app.get("/api/info")
def info():
    forms = [{"id": f, "title": load_schema(f)["title"]} for f in list_schemas()]
    return {"forms": forms, "extractor": type(extractor).__name__}


@app.post("/api/sessions")
def create_session(body: NewSession):
    try:
        schema = load_schema(body.form_id)
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, "unknown form")
    return _state(store.create(schema, body.lang))


@app.post("/api/sessions/{sid}/turn")
def turn(sid: str, body: Turn):
    if body.speaker not in ("operator", "citizen"):
        raise HTTPException(422, "speaker must be operator or citizen")
    s = _session(sid, body.snapshot)
    with s.lock:
        s.add_turn(body.speaker, body.text, extractor)
        return _state(s)


@app.post("/api/sessions/{sid}/edit")
def edit(sid: str, body: Edit):
    s = _session(sid, body.snapshot)
    with s.lock:
        if not s.operator_edit(body.key, body.value):
            raise HTTPException(422, f"invalid value for {body.key}")
        return _state(s)


@app.get("/api/sessions/{sid}/export")
def export(sid: str):
    try:
        return _session(sid).export()
    except PermissionError as e:
        raise HTTPException(409, str(e))


@app.get("/api/sessions/{sid}/slip")
def slip(sid: str):
    try:
        return _session(sid).slip()
    except PermissionError as e:
        raise HTTPException(409, str(e))


@app.post("/api/sessions/{sid}/export")
def export_with_snapshot(sid: str, body: Snap):
    try:
        return _session(sid, body.snapshot).export()
    except PermissionError as e:
        raise HTTPException(409, str(e))


@app.post("/api/sessions/{sid}/slip")
def slip_with_snapshot(sid: str, body: Snap):
    try:
        return _session(sid, body.snapshot).slip()
    except PermissionError as e:
        raise HTTPException(409, str(e))


@app.get("/api/latest-confirmed")
def latest_confirmed():
    """Used by the Chrome extension on the operator's own machine."""
    try:
        return store.latest_confirmed().export()
    except KeyError:
        raise HTTPException(404, "no confirmed application yet")


@app.delete("/api/sessions/{sid}")
def end(sid: str):
    store.delete(sid)
    return {"deleted": True}


@app.get("/sw.js")
def service_worker():
    # Served from the root so it can control the whole app.
    return FileResponse(WEB / "sw.js", media_type="text/javascript")


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


app.mount("/web", StaticFiles(directory=WEB), name="web")
