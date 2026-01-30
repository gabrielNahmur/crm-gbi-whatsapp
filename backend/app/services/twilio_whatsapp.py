"""
Serviço de integração com Twilio WhatsApp API.
"""

import logging
from typing import Optional, Dict, Any
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class TwilioWhatsAppService:
    """Cliente para Twilio WhatsApp API"""
    
    def __init__(self):
        self.account_sid = settings.twilio_account_sid
        self.auth_token = settings.twilio_auth_token
        self.whatsapp_number = settings.twilio_whatsapp_number
        
        if self.account_sid and self.auth_token:
            self.client = Client(self.account_sid, self.auth_token)
        else:
            self.client = None
            logger.warning("Twilio credentials not configured")
    
    def send_message(
        self,
        to: str,
        body: str
    ) -> Dict[str, Any]:
        """
        Envia mensagem de texto via WhatsApp Twilio.
        
        Args:
            to: Número do destinatário (formato: 5511999999999)
            body: Texto da mensagem
        
        Returns:
            Resposta da API
        """
        if not self.client:
            logger.error("Twilio client not initialized")
            return {"success": False, "error": "Twilio not configured"}
        
        # Formata os números para o padrão Twilio
        to_whatsapp = f"whatsapp:+{to.lstrip('+')}"
        from_whatsapp = f"whatsapp:{self.whatsapp_number}"
        
        try:
            message = self.client.messages.create(
                body=body,
                from_=from_whatsapp,
                to=to_whatsapp
            )
            
            logger.info(f"Mensagem Twilio enviada: {message.sid} para {to}")
            
            return {
                "success": True,
                "message_sid": message.sid,
                "status": message.status,
                "to": to
            }
            
        except TwilioRestException as e:
            logger.error(f"Erro Twilio: {e.code} - {e.msg}")
            return {
                "success": False,
                "error_code": e.code,
                "error_message": e.msg
            }
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem Twilio: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def send_message_async(
        self,
        to: str,
        body: str
    ) -> Dict[str, Any]:
        """
        Versão assíncrona do send_message.
        Twilio não tem cliente async nativo, então usamos sync.
        """
        return self.send_message(to, body)


# Singleton
_twilio_service: Optional[TwilioWhatsAppService] = None


def get_twilio_service() -> TwilioWhatsAppService:
    """Retorna instância singleton do serviço Twilio"""
    global _twilio_service
    if _twilio_service is None:
        _twilio_service = TwilioWhatsAppService()
    return _twilio_service
