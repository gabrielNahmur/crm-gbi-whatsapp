"""
Serviço de integração com WhatsApp Business API (Meta).
"""

import httpx
import logging
from typing import Optional, Dict, Any
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def normalize_brazilian_phone(phone: str) -> str:
    """
    Normaliza número de telefone brasileiro para formato correto.
    
    O WhatsApp webhook envia números sem o 9 (ex: 555391629874 - 12 dígitos),
    mas a API de envio requer o 9 (ex: 5553991629874 - 13 dígitos).
    
    Formato esperado: 55 + DDD(2) + 9 + número(8) = 13 dígitos
    Formato recebido: 55 + DDD(2) + número(8) = 12 dígitos
    
    Args:
        phone: Número de telefone (pode ter ou não o 9)
    
    Returns:
        Número normalizado com 13 dígitos
    """
    # Remove qualquer caractere não numérico
    phone = ''.join(filter(str.isdigit, phone))
    
    # Se já tem 13 dígitos e começa com 55, está correto
    if len(phone) == 13 and phone.startswith('55'):
        return phone
    
    # Se tem 12 dígitos e começa com 55, precisa adicionar o 9
    if len(phone) == 12 and phone.startswith('55'):
        # Formato: 55 + DDD(2 dígitos) + número(8 dígitos)
        # Adiciona o 9 após o DDD: 55 + DDD + 9 + número
        ddd = phone[2:4]  # Ex: 53
        numero = phone[4:]  # Ex: 91629874
        phone_normalizado = f"55{ddd}9{numero}"
        logger.info(f"Número normalizado: {phone} -> {phone_normalizado}")
        return phone_normalizado
    
    # Retorna como está se não for padrão brasileiro
    return phone


class WhatsAppService:
    """Cliente para WhatsApp Business API da Meta"""
    
    BASE_URL = "https://graph.facebook.com"
    
    def __init__(self):
        self.phone_number_id = settings.meta_phone_number_id
        self.access_token = settings.meta_access_token
        self.api_version = settings.meta_api_version
        self.api_url = f"{self.BASE_URL}/{self.api_version}/{self.phone_number_id}"
    
    async def send_message(
        self,
        to: str,
        text: str,
        reply_to_message_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Envia mensagem de texto via WhatsApp.
        """
        # Normaliza o número de telefone brasileiro (adiciona 9 se necessário)
        to = normalize_brazilian_phone(to)
        logger.info(f"Sending message to normalized number: {to}")
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": text}
        }
        
        if reply_to_message_id:
            payload["context"] = {"message_id": reply_to_message_id}
        
        return await self._make_request("messages", payload)
    
    async def send_template(
        self,
        to: str,
        template_name: str,
        language: str = "pt_BR",
        components: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Envia mensagem de template.
        """
        to = normalize_brazilian_phone(to)
        logger.info(f"Sending template to normalized number: {to}")

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language}
            }
        }
        
        if components:
            payload["template"]["components"] = components
        
        return await self._make_request("messages", payload)
    
    async def send_media(
        self,
        to: str,
        media_type: str,
        media_url: str,
        caption: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Envia mídia.
        """
        to = normalize_brazilian_phone(to)
        logger.info(f"Sending media to normalized number: {to}")

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": media_type,
            media_type: {
                "link": media_url
            }
        }
        
        if caption and media_type in ["image", "video"]:
            payload[media_type]["caption"] = caption
        
        return await self._make_request("messages", payload)
    
    async def mark_as_read(self, message_id: str) -> Dict[str, Any]:
        """
        Marca mensagem como lida.
        
        Args:
            message_id: ID da mensagem do WhatsApp
        
        Returns:
            Resposta da API
        """
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }
        
        return await self._make_request("messages", payload)
    
    async def _make_request(
        self,
        endpoint: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Faz requisição para a API do WhatsApp"""
        url = f"{self.api_url}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                logger.info(f"WhatsApp API response: {result}")
                return result
            except httpx.HTTPError as e:
                logger.error(f"WhatsApp API error: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    logger.error(f"Response: {e.response.text}")
                raise


# Instância global
whatsapp_service = WhatsAppService()


def get_whatsapp_service() -> WhatsAppService:
    """Retorna instância do serviço WhatsApp"""
    return whatsapp_service
