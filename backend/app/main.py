"""
Aplicação principal FastAPI - WhatsApp CRM
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging

from app.config import get_settings
from app.database.postgres import init_db, close_db
from app.database.redis_client import init_redis, close_redis
from app.api.routes import webhook, messages, conversations, agents, auth
from app.api.websocket import router as websocket_router

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida da aplicação"""
    # Startup
    logger.info("🚀 Iniciando WhatsApp CRM...")
    await init_db()
    await init_redis()
    logger.info(f"🔑 Secret Key Prefix: {settings.secret_key[:5]}...")
    logger.info(f"📂 Database URL: {settings.database_url}")
    logger.info("✅ Banco de dados e Redis conectados")
    
    yield
    
    # Shutdown
    logger.info("🛑 Encerrando WhatsApp CRM...")
    await close_db()
    await close_redis()
    logger.info("👋 Aplicação encerrada")


# Criação da aplicação
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Sistema de CRM e Atendimento via WhatsApp com IA",
    lifespan=lifespan
)

# Configuração de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8002",
        "http://127.0.0.1:8002",
        "*" # Fallback para dev, mas credential precisa de origin especifico
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rotas da API
app.include_router(auth.router, prefix="/api/auth", tags=["Autenticação"])
app.include_router(webhook.router, prefix="/api/webhook", tags=["Webhook WhatsApp"])
app.include_router(messages.router, prefix="/api/messages", tags=["Mensagens"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["Conversas"])
app.include_router(agents.router, prefix="/api/agents", tags=["Atendentes"])
app.include_router(websocket_router, prefix="/ws", tags=["WebSocket"])


@app.get("/api/health")
async def health_check():
    """Endpoint de health check"""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version
    }


@app.get("/api")
async def api_info():
    """Informações da API"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "redoc": "/redoc"
    }


# Servir frontend estático (React build)
# Descomente após build do frontend
# app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")
