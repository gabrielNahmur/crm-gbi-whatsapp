"""
Rota de Webhook para receber mensagens do WhatsApp.
"""

import logging
import traceback
from fastapi import APIRouter, Request, HTTPException, Depends, Query, BackgroundTasks, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.postgres import get_db, async_session
from app.services.bot_engine import BotEngine

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


@router.get("")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    """
    Verificação do webhook pelo Meta.
    A Meta envia uma requisição GET para verificar o webhook.
    """
    logger.info(f"Webhook verification: mode={hub_mode}, token={hub_verify_token}")
    
    if hub_mode == "subscribe" and hub_verify_token == settings.meta_webhook_verify_token:
        logger.info("Webhook verified successfully")
        return int(hub_challenge)
    
    logger.warning("Webhook verification failed")
    raise HTTPException(status_code=403, detail="Verification failed")


async def _process_message_background(
    message: dict,
    contact_name: str = None,
    use_twilio: bool = False
):
    """Executa processamento do bot em background com nova sessão"""
    logger.info(f"BACKGROUND: Iniciando processamento para {message.get('id')}")
    import json
    # DEBUG EXTREMO: Salvar arquivo também na background task para garantir
    try:
        with open("debug_background_payload.json", "w") as f:
            json.dump(message, f, indent=2)
    except:
        pass

    async with async_session() as session:
        try:
            message_type = message.get("type", "text")
            message_id = message.get("id") or message.get("MessageSid")
            phone = message.get("from")
            
            # Ajustes específicos para Twilio/Meta payload
            # (Lógica extraída de _process_message original e adaptada)
            content = ""
            media_url = None
            
            if use_twilio:
                content = message.get("body", "")
            else:
                # Meta payload extraction logic
                if message_type == "text":
                    content = message.get("text", {}).get("body", "")
                elif message_type == "image":
                    content = message.get("image", {}).get("caption", "[Imagem]")
                elif message_type == "audio":
                    content = "[Áudio]"
                else:
                    content = f"[{message_type}]"

            if not content:
                logger.warning(f"Empty content for message {message_id}")
                return

            bot = BotEngine(session, use_twilio=use_twilio)
            await bot.process_incoming_message(
                phone=phone,
                message_text=content,
                message_id=message_id,
                sender_name=contact_name,
                message_type=message_type,
                media_url=media_url
            )
            await session.commit()
            
        except Exception as e:
            logger.error(f"Background processing error: {e}")
            await session.rollback()


@router.post("")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Recebe mensagens do WhatsApp via webhook (Meta).
    """
    try:
        body = await request.json()
        
        if body.get("object") != "whatsapp_business_account":
            return {"status": "ignored"}
        
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                if change.get("field") != "messages":
                    continue
                
                value = change.get("value", {})
                contacts = value.get("contacts", [])
                contact_name = None
                if contacts:
                    contact_name = contacts[0].get("profile", {}).get("name")
                
                for message in value.get("messages", []):
                    # Adiciona task em background
                    message["from"] = message.get("from") # Ensure phone
                    background_tasks.add_task(
                        _process_message_background,
                        message=message,
                        contact_name=contact_name,
                        use_twilio=False
                    )
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return {"status": "error"}


@router.post("/twilio")
async def receive_twilio_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Recebe mensagens do WhatsApp via Twilio webhook.
    """
    try:
        form_data = await request.form()
        data = dict(form_data)
        
        logger.info(f"Twilio webhook received: {data}")
        
        # DEBUG: Salva último payload (Restaurado)
        import json
        try:
            with open("last_twilio_webhook.json", "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Erro ao salvar debug json: {e}")
        
        from_number = data.get("From", "").replace("whatsapp:", "").lstrip("+")
        body = data.get("Body", "")
        message_sid = data.get("MessageSid", "")
        profile_name = data.get("ProfileName", None)
        
        if not body or not from_number:
            return Response(content="", media_type="text/xml")
            
        # Payload normalizado para background
        message_payload = {
            "type": "text",
            "id": message_sid,
            "from": from_number,
            "body": body
        }
        
        background_tasks.add_task(
            _process_message_background,
            message=message_payload,
            contact_name=profile_name,
            use_twilio=True
        )
        
        return Response(content="", media_type="text/xml")
        
    except Exception as e:
        logger.error(f"Error processing Twilio webhook: {e}")
        return Response(content="", media_type="text/xml")
