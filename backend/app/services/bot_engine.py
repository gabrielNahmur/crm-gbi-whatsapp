"""
Bot Engine - Lógica principal do chatbot.
"""

import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings, INTENT_TO_SECTOR
from app.services.whatsapp import get_whatsapp_service
from app.services.openai_service import get_openai_service
from app.database.redis_client import get_redis, ContextManager, QueueManager, DebounceManager
from app.models import Lead, Conversation, Message, VALID_SECTORS
import time
import asyncio
from app.api.websocket import notify_new_message, notify_new_conversation

logger = logging.getLogger(__name__)
settings = get_settings()


class BotEngine:
    """Motor principal do chatbot"""
    
    def __init__(self, db: AsyncSession, use_twilio: bool = False):
        self.db = db
        self.use_twilio = True # FORCE TWILIO DEBUG
        logger.info(f"BotEngine init: use_twilio={self.use_twilio} (Settings: {settings.use_twilio})")
        
        # Escolhe o serviço de envio baseado na configuração
        if self.use_twilio:
            from app.services.twilio_whatsapp import get_twilio_service
            self.messenger = get_twilio_service()
            logger.info("BotEngine usando Twilio para envio")
        else:
            self.messenger = get_whatsapp_service()
            logger.info("BotEngine usando Meta WhatsApp API para envio")
        
        self.whatsapp = get_whatsapp_service()  # Mantém para compatibilidade
        self.openai = get_openai_service()
        self.redis = get_redis()
        self.context_manager = ContextManager(self.redis)
        self.queue_manager = QueueManager(self.redis)
        self.debounce_manager = DebounceManager(self.redis)
    
    async def process_incoming_message(
        self,
        phone: str,
        message_text: str,
        message_id: str,
        sender_name: Optional[str] = None,
        message_type: str = "text",
        media_url: Optional[str] = None
    ) -> None:
        """
        Processa mensagem recebida do WhatsApp.
        """
        logger.info(f"Processando mensagem de {phone}: {message_text[:50]}...")
        
        # 1. Busca ou cria lead
        lead = await self._get_or_create_lead(phone, sender_name)
        
        # 2. Busca ou cria conversa ativa
        conversation = await self._get_or_create_conversation(lead)
        
        # 3. Salva mensagem do cliente
        customer_message = Message(
            conversation_id=conversation.id,
            sender_type="customer",
            sender_id=phone,
            content=message_text,
            message_type=message_type,
            media_url=media_url,
            whatsapp_message_id=message_id
        )
        self.db.add(customer_message)
        # Commit imediato para garantir que a mensagem seja salva
        # mesmo se houver erro no processamento do bot/IA
        await self.db.commit()
        await self.db.refresh(customer_message)
        
        # 4. Adiciona ao contexto Redis
        try:
            await self.context_manager.add_message(phone, "user", message_text)
        except Exception as e:
            logger.error(f"Erro ao adicionar ao Redis: {e}")
        
        # === INÍCIO LOGICA DE DEBOUNCE ===
        # Salva timestamp atual para este telefone
        current_ts = time.time()
        await self.debounce_manager.set_last_message_time(phone, current_ts)
        
        # Espera um pouco para ver se chegam mais mensagens
        logger.info(f"Aguardando debounce para {phone}...")
        await asyncio.sleep(2.0) # 2 segundos de buffer
        
        # Verifica se chegou mensagem mais nova enquanto dormia
        last_ts = await self.debounce_manager.get_last_message_time(phone)
        
        if last_ts > current_ts:
            logger.info(f"Nova mensagem detectada para {phone}. Abortando processamento anterior.")
            return # Aborta, deixa a próxima task processar tudo junto
            
        logger.info(f"Debounce finalizado para {phone}. Processando contexto agrupado.")
        # === FIM LOGICA DE DEBOUNCE ===

        # 5. Verifica se conversa já está com atendente
        if conversation.status == "in_progress":
            # Já tem atendente, não processa com bot
            logger.info(f"Conversa {conversation.id} já está com atendente")
            return
        
        # 6. Processa com IA
        try:
            context = await self.context_manager.get_context(phone)
            is_business_hours = self._is_business_hours()
            
            ai_response = await self.openai.analyze_and_respond(
                message=message_text,
                context=context[:-1] if len(context) > 1 else None,
                customer_name=lead.name,
                is_business_hours=is_business_hours
            )
            
            # === ANTI-DUPLICAÇÃO ===
            response_text = ai_response["response"]
            
            # Smart Dedup: Se a resposta contiver links do App, usa key estática
            # Isso previne "Não informo preços + App" vs "Veja no App" (mesma intent prática)
            dedup_key = response_text
            dedup_ttl = 15
            
            if "play.google.com" in response_text or "apps.apple.com" in response_text:
                dedup_key = "STATIC_KEY:APP_LINKS"
                dedup_ttl = 60 # 1 minuto de silêncio se já mandou o link do app
            
            is_duplicate = await self.debounce_manager.check_duplicate_response(phone, dedup_key, ttl=dedup_ttl)
            
            if is_duplicate:
                logger.warning(f"Resposta duplicada detectada para {phone}. Ignorando envio.")
                return
            # =======================
            
            # 7. Atualiza intent da mensagem e conversa
            # Note: Precisamos fazer um novo merge ou buscar se a sessão foi resetada,
            # mas com expire_on_commit=False, deve estar ok.
            customer_message.intent = ai_response["intent"]
            conversation.intent = ai_response["intent"]
            
            # 8. Mapeia intent para setor
            sector = self._map_intent_to_sector(ai_response["intent"])
            old_sector = conversation.sector  # Guarda setor antigo ANTES de atualizar
            
            self.db.add(customer_message)
            self.db.add(conversation)
            
            # 9. Envia resposta do bot
            try:
                if self.use_twilio:
                    # Twilio não suporta reply_to_message_id
                    await self.messenger.send_message_async(
                        to=phone,
                        body=ai_response["response"]
                    )
                else:
                    await self.messenger.send_message(
                        to=phone,
                        text=ai_response["response"],
                        reply_to_message_id=message_id
                    )
            except Exception as e:
                logger.error(f"Erro ao enviar mensagem: {e}")
                # Não abortamos, pois queremos salvar a resposta do bot no banco
                
            # 10. Salva resposta do bot
            bot_message = Message(
                conversation_id=conversation.id,
                sender_type="bot",
                sender_id="bot",
                content=ai_response["response"],
                message_type="text",
                intent=ai_response["intent"]
            )
            self.db.add(bot_message)
            
            # 11. Adiciona resposta ao contexto
            await self.context_manager.add_message(phone, "assistant", ai_response["response"])
            
            # 12. Se precisa de atendente humano
            if ai_response["needs_human"]:
                await self._transfer_to_queue(conversation, sector, old_sector)
            elif sector:
                # Se não precisa de humano mas tem setor, atualiza
                conversation.sector = sector
            
            # 13. Marca mensagem como lida (apenas para Meta API)
            if not self.use_twilio:
                try:
                    await self.whatsapp.mark_as_read(message_id)
                except Exception as e:
                    logger.warning(f"Não foi possível marcar como lida: {e}")
                
            await self.db.commit()
            
            # 14. Notifica via WebSocket para atualização em tempo real
            sector_to_notify = conversation.sector or "comercial"
            try:
                await notify_new_message(conversation.id, sector_to_notify, customer_message.to_dict())
                await notify_new_message(conversation.id, sector_to_notify, bot_message.to_dict())
            except Exception as ws_err:
                logger.warning(f"Erro ao notificar WebSocket: {ws_err}")
            
            logger.info(f"Mensagem processada com sucesso. Intent: {ai_response['intent']}")
            
        except Exception as e:
            logger.error(f"Erro no processamento do Bot: {e}", exc_info=True)
            # Tentar enviar mensagem de erro genérica se possível?
            # Por enquanto apenas logamos para não perder a mensagem original salva.
    
    async def send_agent_message(
        self,
        conversation_id: int,
        agent_id: int,
        message_text: str
    ) -> Message:
        """
        Envia mensagem de um atendente.
        """
        # Busca conversa
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()
        
        if not conversation:
            raise ValueError(f"Conversa {conversation_id} não encontrada")
        
        # Busca lead para pegar telefone
        result = await self.db.execute(
            select(Lead).where(Lead.id == conversation.lead_id)
        )
        lead = result.scalar_one()
        
        # Envia via WhatsApp (usando o serviço correto: Twilio ou Meta)
        if self.use_twilio:
            # Twilio usa 'body' como parâmetro
            result = await self.messenger.send_message_async(to=lead.phone, body=message_text)
            if not result.get('success'):
                raise Exception(f"Erro Twilio: {result.get('error', result.get('error_message', 'Unknown'))}")
        else:
            # Meta usa 'text' como parâmetro
            await self.whatsapp.send_message(to=lead.phone, text=message_text)
        
        # Salva mensagem
        message = Message(
            conversation_id=conversation_id,
            sender_type="agent",
            sender_id=str(agent_id),
            content=message_text,
            message_type="text"
        )
        self.db.add(message)
        
        # Adiciona ao contexto
        await self.context_manager.add_message(lead.phone, "assistant", message_text)
        
        await self.db.commit()
        
        # Notifica via WebSocket para atualização em tempo real
        sector_to_notify = conversation.sector or "comercial"
        try:
            await notify_new_message(conversation.id, sector_to_notify, message.to_dict())
        except Exception as ws_err:
            logger.warning(f"Erro ao notificar WebSocket (agent): {ws_err}")
        
        return message
    
    async def _get_or_create_lead(
        self,
        phone: str,
        name: Optional[str] = None
    ) -> Lead:
        """Busca ou cria lead pelo telefone"""
        result = await self.db.execute(
            select(Lead).where(Lead.phone == phone)
        )
        lead = result.scalar_one_or_none()
        
        if not lead:
            lead = Lead(phone=phone, name=name)
            self.db.add(lead)
            await self.db.flush()
            logger.info(f"Novo lead criado: {phone}")
        else:
            # Atualiza nome se fornecido e lead não tem nome
            if name and not lead.name:
                lead.name = name
            lead.last_contact = datetime.utcnow()
        
        return lead
    
    async def _get_or_create_conversation(self, lead: Lead) -> Conversation:
        """Busca conversa ativa ou cria nova. Reativa resolved se recente."""
        from datetime import timedelta
        from sqlalchemy import or_
        
        # Primeiro busca conversa ativa (não fechada/resolvida)
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.lead_id == lead.id)
            .where(Conversation.status.not_in(["resolved", "closed"]))
            .order_by(Conversation.started_at.desc())
        )
        conversation = result.scalar_one_or_none()
        
        if conversation:
            return conversation
        
        # Se não há ativa, busca conversa resolvida recentemente
        # Usa started_at como fallback se resolved_at for NULL
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.lead_id == lead.id)
            .where(Conversation.status == "resolved")
            .where(
                or_(
                    Conversation.resolved_at > cutoff_time,
                    Conversation.started_at > cutoff_time
                )
            )
            .order_by(Conversation.started_at.desc())
        )
        resolved_conv = result.scalar_one_or_none()
        
        if resolved_conv:
            # Reativa a conversa - volta para o bot
            resolved_conv.status = "bot_handling"
            resolved_conv.resolved_at = None
            resolved_conv.agent_id = None  # Remove atribuição ao atendente
            
            # Limpa setor e intenção anteriores para começar neutro
            resolved_conv.sector = None
            resolved_conv.intent = None
            
            logger.info(f"Conversa {resolved_conv.id} reativada (era resolved)")
            return resolved_conv
        
        # Nenhuma conversa encontrada - cria nova
        conversation = Conversation(
            lead_id=lead.id,
            status="bot_handling"
        )
        self.db.add(conversation)
        await self.db.flush()
        
        # Incrementa contador de conversas do lead
        lead.total_conversations += 1
        
        logger.info(f"Nova conversa criada: {conversation.id}")
        
        return conversation
    
    async def _transfer_to_queue(
        self,
        conversation: Conversation,
        sector: Optional[str],
        old_sector: Optional[str] = None
    ) -> None:
        """Transfere conversa para fila de atendimento"""
        # Define setor (default: suporte)
        if not sector:
            sector = "suporte"
        
        was_already_in_queue = conversation.status == "waiting_queue"
        
        # Se já estava na fila e mudou de setor, apenas atualiza
        if was_already_in_queue:
            if old_sector != sector:
                logger.info(f"Conversa {conversation.id} mudou de setor: {old_sector} -> {sector}")
                conversation.sector = sector
                
                # Atualiza filas no Redis
                try:
                    # Remove da fila antiga (se existir e old_sector for válido)
                    if old_sector:
                        await self.queue_manager.remove_from_queue(old_sector, conversation.id)
                    
                    # Adiciona nova fila
                    await self.queue_manager.add_to_queue(sector, conversation.id)
                    
                    # Notifica mudança nas filas via WebSocket
                    from app.api.websocket import notify_queue_update
                    await notify_queue_update()
                    
                except Exception as e:
                    logger.error(f"Erro ao atualizar filas Redis: {e}")
            else:
                logger.info(f"Conversa {conversation.id} já está na fila do setor {sector}")
            return
        
        # Novo item na fila
        conversation.status = "waiting_queue"
        conversation.sector = sector
        
        # Adiciona à fila Redis
        await self.queue_manager.add_to_queue(sector, conversation.id)
        
        # Notifica
        try:
            from app.api.websocket import notify_queue_update
            await notify_queue_update()
        except Exception as e:
            logger.error(f"Erro ao notificar WS queue: {e}")
        
        logger.info(f"Conversa {conversation.id} adicionada à fila {sector}")
    
    def _map_intent_to_sector(self, intent: str) -> Optional[str]:
        """Mapeia intenção para setor"""
        intent_lower = intent.lower()
        
        # Busca no mapeamento
        if intent_lower in INTENT_TO_SECTOR:
            return INTENT_TO_SECTOR[intent_lower]
        
        # Se a intenção já é um setor válido
        if intent_lower in VALID_SECTORS:
            return intent_lower
        
        return None
    
    def _is_business_hours(self) -> bool:
        """Verifica se está em horário comercial"""
        now = datetime.now()
        weekday = now.weekday()  # 0=segunda, 6=domingo
        current_time = now.strftime("%H:%M")
        
        # Domingo
        if weekday == 6:
            return settings.trabalha_domingo
        
        # Sábado
        if weekday == 5:
            if not settings.trabalha_sabado:
                return False
            return settings.horario_inicio <= current_time <= settings.horario_fim_sabado
        
        # Segunda a Sexta
        return settings.horario_inicio <= current_time <= settings.horario_fim
