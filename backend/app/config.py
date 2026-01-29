"""
Configurações da aplicação.
Carrega variáveis de ambiente e define constantes.
"""

from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache
from dotenv import load_dotenv
import os

# Força carregamento do .env
load_dotenv()


class Settings(BaseSettings):
    """Configurações carregadas do arquivo .env"""
    
    # Aplicação
    app_name: str = "WhatsApp CRM"
    app_version: str = "1.0.0"
    debug: bool = False
    secret_key: str = "sua-chave-secreta-aqui-mude-em-producao"
    
    # Meta WhatsApp API
    meta_phone_number_id: str = ""
    meta_access_token: str = ""
    meta_webhook_verify_token: str = "token-verificacao-webhook"
    meta_api_version: str = "v18.0"
    meta_business_account_id: str = ""
    
    # Twilio WhatsApp API
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_number: str = "+14155238886"  # Sandbox number
    use_twilio: bool = True  # Usar Twilio em vez de Meta
    
    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/whatsapp_crm"
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # Horário comercial
    horario_inicio: str = "08:00"
    horario_fim: str = "18:00"
    trabalha_sabado: bool = True
    horario_fim_sabado: str = "12:00"
    trabalha_domingo: bool = False
    
    # Contexto da IA
    max_context_messages: int = 10
    context_ttl_hours: int = 24
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Retorna instância cacheada das configurações"""
    return Settings()


# Setores disponíveis
# Setores disponíveis
SETORES = [
    "comercial",
    "compras",
    "contas_pagar",
    "contas_receber",
    "rh",
    "atendimento_humano",
    "geral",
    "outros"
]

# Mapeamento de intenções para setores
INTENT_TO_SECTOR = {
    "comercial": "comercial",
    "compras": "compras",
    "contas_pagar": "contas_pagar",
    "contas_receber": "contas_receber",
    "rh": "rh",
    "atendente": "atendimento_humano",
    "geral": "geral",
    "outros": "outros"
}
