"""Native frontend with a same-origin local API proxy; no GPU worker here."""
import os
from pathlib import Path
from contextlib import asynccontextmanager
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

@asynccontextmanager
async def lifespan(app):
    async with httpx.AsyncClient(base_url=os.getenv('API_URL','http://127.0.0.1:8000'), timeout=620, trust_env=False) as client:
        app.state.api = client
        yield

app = FastAPI(docs_url=None, redoc_url=None, lifespan=lifespan)

@app.get('/_stcore/health')
async def health():
    return Response('ok')

@app.api_route('/api/{path:path}', methods=['GET','POST'])
async def proxy(path: str, request: Request):
    if path.startswith('/') or '..' in path.split('/'):
        return Response('Invalid path',status_code=400)
    raw = await request.body()
    if len(raw) > 11 * 1024 * 1024:
        return Response('Archivo demasiado grande',status_code=413)
    try:
        response = await request.app.state.api.request(request.method,'/' + path,
            params=request.query_params,content=raw,
            headers={'content-type': request.headers.get('content-type','application/json')})
        return Response(response.content,status_code=response.status_code,
                        headers={'content-type':response.headers.get('content-type','application/octet-stream')})
    except httpx.RequestError:
        return Response('{"detail":"No fue posible conectar con el motor local"}',status_code=503,media_type='application/json')

app.mount('/assets',StaticFiles(directory=ROOT/'web/assets'),name='assets')
app.mount('/examples',StaticFiles(directory=ROOT/'app/assets/portraits'),name='examples')
app.mount('/characters',StaticFiles(directory=ROOT/'app/assets/characters',check_dir=False),name='characters')

@app.get('/')
@app.get('/studio')
@app.get('/es/ai-influencer')
@app.get('/es/ai-influencer-studio')
async def index():
    return FileResponse(ROOT/'web/index.html',headers={'cache-control':'no-cache'})
