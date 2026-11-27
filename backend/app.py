"""FastAPI server: browser does speech-to-text and text-to-speech; the server turns
transcript segments into a checked form."""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .dialog import SessionStore
from .extractor import make_extractor
from .schema import list_schemas, load_schema

WEB = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="Bol Ke Bharo")
store = SessionStore()
extractor = make_extractor()


class NewSession(BaseModel):
    form_id: str = "pension_up"
    lang: str = "hi"


class Turn(BaseModel):
    speaker: str  # "operator" | "citizen"
    text: str


class Edit(BaseModel):
    key: str
    value: str


def _session(sid):
    try:
        return store.get(sid)
    except KeyError:
        raise HTTPException(404, "session expired or not found")


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
    return store.create(schema, body.lang).public_state()


@app.post("/api/sessions/{sid}/turn")
def turn(sid: str, body: Turn):
    if body.speaker not in ("operator", "citizen"):
        raise HTTPException(422, "speaker must be operator or citizen")
    s = _session(sid)
    with s.lock:
        s.add_turn(body.speaker, body.text, extractor)
        return s.public_state()


@app.post("/api/sessions/{sid}/edit")
def edit(sid: str, body: Edit):
    s = _session(sid)
    with s.lock:
        if not s.operator_edit(body.key, body.value):
            raise HTTPException(422, f"invalid value for {body.key}")
        return s.public_state()


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


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


app.mount("/web", StaticFiles(directory=WEB), name="web")
