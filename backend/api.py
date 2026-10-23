"""Authenticated localhost API. Not publicly exposed during initial development."""
import asyncio
from contextlib import asynccontextmanager
import json
import secrets
import uuid
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from .auth import COOKIE, Sessions
from .config import ROOT
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from .agent import Engine
from .control import DesktopControl
from .linux_status import LinuxStatus
from .config import Settings
from .executor import LinuxExecutor
from .inference import OllamaProvider
from .store import Store

class TaskRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request: str = Field(min_length=1, max_length=8000)

class Login(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=512)

class Ownership(BaseModel):
    model_config = ConfigDict(extra='forbid',strict=True)
    owner: str = Field(pattern='^(agent|human)$')

class Automation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    routine_commands: bool

class Decision(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    approval_id: str
    allow: bool


def create_app(settings=None, provider=None, executor=None):
    settings = settings or Settings.load()
    store = Store(settings.database)
    provider = provider or OllamaProvider(settings)
    executor = executor or LinuxExecutor(settings)
    readiness = LinuxStatus(executor)
    control = DesktopControl(executor)
    engine = Engine(store, provider, executor, control)
    control.interrupt = engine.interrupt_tools
    @asynccontextmanager
    async def lifespan(app):
        await control.initialize()
        yield
        await engine.close()
        store.db.close()
    app = FastAPI(title='LocalPilot', lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.engine, app.state.store = engine, store
    bearer = HTTPBearer(auto_error=False)
    sessions = Sessions(settings)

    @app.middleware('http')
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action 'self'"
        response.headers['Cache-Control'] = 'no-store'
        return response

    async def authenticate(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credentials:
            if secrets.compare_digest(credentials.credentials, settings.token):
                return
            raise HTTPException(401, 'Authentication required')
        if not sessions.valid(request):
            raise HTTPException(401, 'Authentication required')
        if request.method not in ('GET', 'HEAD'):
            sessions.check_origin(request)

    @app.get('/sw.js')
    async def service_worker():
        return FileResponse(ROOT / 'frontend/sw.js',media_type='application/javascript',headers={'Service-Worker-Allowed':'/'})

    @app.get('/')
    async def frontend():
        return FileResponse(ROOT / 'frontend/index.html')

    @app.post('/session')
    async def login(request: Request, body: Login):
        if not settings.password_hash:
            raise HTTPException(503, 'Browser sign-in is not configured')
        value = sessions.login(request, body.username, body.password)
        response = JSONResponse({'signed_in': True})
        response.set_cookie(COOKIE, value, secure=True, httponly=True, samesite='strict', max_age=43200, path='/')
        return response

    @app.delete('/session', dependencies=[Depends(authenticate)])
    async def logout(request: Request):
        sessions.logout(request)
        response = JSONResponse({'signed_out': True})
        response.delete_cookie(COOKIE, secure=True, httponly=True, samesite='strict', path='/')
        return response

    @app.get('/tasks', dependencies=[Depends(authenticate)])
    async def recent_tasks():
        return store.recent()

    def task(task_id):
        row = store.get(task_id)
        if not row:
            raise HTTPException(404, 'Task not found')
        return row

    @app.get('/health', dependencies=[Depends(authenticate)])
    async def health():
        return {'status': 'ok', 'execution_account': 'pilot', 'model': settings.model}

    @app.get('/linux/status', dependencies=[Depends(authenticate)])
    async def linux_status():
        return await readiness.get()

    @app.get('/desktop/state', dependencies=[Depends(authenticate)])
    async def desktop_state():
        return control.state()

    @app.post('/desktop/control', dependencies=[Depends(authenticate)])
    async def desktop_control(body: Ownership):
        try:return await control.change(body.owner)
        except Exception as error:raise HTTPException(503,str(error)) from error

    @app.get('/screenshots/{image_id}', dependencies=[Depends(authenticate)])
    async def screenshot(image_id: str):
        try:image_id=str(uuid.UUID(image_id))
        except ValueError:raise HTTPException(404,'Screenshot not found')
        path=ROOT / '.local/screenshots' / (image_id+'.jpg')
        if not path.is_file():raise HTTPException(404,'Screenshot not found')
        return FileResponse(path,media_type='image/jpeg')

    @app.get('/settings/automation', dependencies=[Depends(authenticate)])
    async def automation_settings():
        return {'routine_commands':store.routine_approval(),'policy':'routine-v1'}

    @app.post('/settings/automation', dependencies=[Depends(authenticate)])
    async def change_automation(body: Automation):
        store.set_routine_approval(body.routine_commands)
        return {'routine_commands':store.routine_approval(),'policy':'routine-v1'}

    @app.get('/models', dependencies=[Depends(authenticate)])
    async def models():
        return await provider.models()

    @app.post('/tasks', status_code=202, dependencies=[Depends(authenticate)])
    async def create_task(body: TaskRequest):
        if len(engine.running) >= 8:
            raise HTTPException(429, 'Task queue is full')
        return {'id': engine.submit(body.request)}

    @app.get('/tasks/{task_id}', dependencies=[Depends(authenticate)])
    async def get_task(task_id: str):
        result = task(task_id)
        pending = engine.pending.get(task_id)
        if pending:
            result['approval'] = {key: value for key, value in pending.items() if key != 'future'}
        return result

    @app.get('/tasks/{task_id}/events', dependencies=[Depends(authenticate)])
    async def events(task_id: str, after: int = 0):
        task(task_id)
        return store.events(task_id, after)

    @app.get('/tasks/{task_id}/stream', dependencies=[Depends(authenticate)])
    async def stream(task_id: str, request: Request, after: int = 0):
        task(task_id)
        try:
            resume = max(after, int(request.headers.get('last-event-id', '0')))
        except ValueError:
            raise HTTPException(400, 'Invalid event cursor')
        async def generate():
            cursor = resume
            while not await request.is_disconnected():
                rows = store.events(task_id, cursor)
                for row in rows:
                    cursor = row['id']
                    yield f'id: {cursor}\nevent: {row["kind"]}\ndata: {json.dumps(row["data"])}\n\n'
                if not rows and task(task_id)['status'] in ('completed', 'failed', 'cancelled', 'interrupted', 'rejected'):
                    break
                if not rows:
                    yield ': heartbeat\n\n'
                await asyncio.sleep(.25)
        return StreamingResponse(generate(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache'})

    @app.post('/tasks/{task_id}/approval', dependencies=[Depends(authenticate)])
    async def approval(task_id: str, body: Decision):
        task(task_id)
        try:
            engine.decide(task_id, body.approval_id, body.allow)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        return {'accepted': True}

    @app.post('/tasks/{task_id}/cancel', dependencies=[Depends(authenticate)])
    async def cancel(task_id: str):
        task(task_id)
        try:
            await engine.cancel(task_id)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        return {'cancelled': True}

    app.mount('/assets', StaticFiles(directory=ROOT / 'frontend'), name='assets')
    return app
