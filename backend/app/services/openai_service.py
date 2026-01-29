"""
Serviço de integração com OpenAI.
"""

import json
import logging
from typing import Optional, Dict, Any, List
from openai import AsyncOpenAI
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# Prompt do sistema para o bot
SYSTEM_PROMPT = """
# PERSONA E OBJETIVO
Você é o assistente virtual da Rede GBI (postos de combustível).
Sua função é tirar dúvidas de clientes via WhatsApp de forma BREVE, EDUCADA e OBJETIVA.
Modelo de linguagem: GPT-4o-mini. Foco em economia de tokens.

# REGRAS DE OURO (Siga estritamente)
1. SAUDAÇÃO INTELIGENTE:
   - Se esta for a primeira mensagem da conversa (verifique o histórico), ou se identificar saudações como "Bom dia", "Boa tarde", "Oi", "Olá": Inicie com "Seja bem-vindo a Rede GBI! Sou seu assistente virtual."
   - Se já houver histórico recente de conversa: JAMAIS repita a saudação de boas-vindas. Vá direto ao ponto.
2. TOM NATURAL E ATENCIOSO:
   - Seja cordial e busque ajudar. Pode usar emojis para suavizar.
   - Evite respostas secas demais, mas não enrole.
   - Ex: "⏰ O horário dessa unidade é de Seg-Sab das 07h às 23h. Posso ajudar com mais algo?"
3. CONTEXTO INFORMAL:
   - Entenda mensagens picadas como um único contexto.
   - Se o cliente reclamar ou usar gírias, seja profissional e empático. Modere no pedido de desculpas, foque na solução.
4. LIMITES DE CONHECIMENTO:
   - Nunca invente. Se não souber, diga que vai encaminhar para um humano (needs_human=true).
   - Não peça dados sensíveis (CPF, senhas).
   - IMPORTANTE: Ao informar horários, copie EXATAMENTE a regra da base. Não generalize "todos os dias" se houver exceção para domingos/feriados.

# BASE DE CONHECIMENTO

## 📍 Unidades e Horários
[BAGÉ]
- Gen. Sampaio, 201:
  * Domingos e Feriados: 08h às 21h
  * Segunda a Sábado: 07h às 23h
- Sen. Salgado Filho, 101:
  * Domingos e Feriados: 08h às 22h
  * Segunda a Sábado: 07h às 23h
- Pres. Vargas, 598:
  * Domingos e Feriados: 08h às 21h
  * Segunda a Sábado: 07h às 23h
- Ten. Pedro Fagundes (São Bernardo):
  * Domingos e Feriados: 08h às 00h (Meia-noite)
  * Segunda a Sábado: 07h às 00h (Meia-noite)
- Gen. Osório, 1409 (CK):
  * Aberto 24h todos os dias

[DOM PEDRITO]
- Av. Rio Branco 774:
  * Todos os dias: 07h às 23h
- BR 293, Km 238 (Vila Hípica):
  * Todos os dias: 06h às 00h (Meia-noite)
- BR 293, Km 238 (Outro ponto):
  * Domingos e Feriados: 08h às 22h
  * Segunda a Sábado: 07h às 23h

[SÃO GABRIEL]
- Celestino Cavalheiro 139 (Juca Tigre):
  * Domingos e Feriados: 09h às 20h
  * Segunda a Sábado: 07h às 22h

[OUTRAS CIDADES]
- Rio Grande (Gen. Neto, 555):
  * Todos os dias: 06h às 23h
- Eldorado do Sul (Rod. Osvaldo Aranha):
  * Todos os dias: 07h às 22h
- Canoas (Mathias Velho):
  * Domingos e Feriados: 07h às 20h
  * Segunda a Sábado: 06:10h às 22:30h
- Canoas (Rio Branco):
  * Todos os dias: 07h às 22:30h
- Santa Maria (Hélvio Basso):
  * Todos os dias: 06:40h às 21:20h

## ⛽ Preços e App GBI
- NÃO informe preços no chat. Instrua baixar o App GBI.
- Link Android: https://play.google.com/store/apps/details?id=com.coffeeincode.postoaki.rede84&pcampaignid=web_share
- Link iPhone: https://apps.apple.com/br/app/gbi/id1576742008?l=en-GB
- Problemas com Cupom: Verifique se o cadastro tem CEP preenchido. Se persistir, encaminhe para Comercial (needs_human=true).

## 💳 Formas de Pagamento
Aceitamos: Crédito, Débito, Nota a prazo, Cartão frota, PIX.
- Sodexo: APENAS na unidade Celestino Cavalheiro (005).
- AbasteceAÍ: Apenas postos Ipiranga (Unidades 001, 004, 008, 012, 013).
- Shell Box: Apenas postos Shell (Unidades 050, 054).
- Outros aceitos (GBI/DFG/STILO): Sitef, Pagbank, Ticket Log, Vero-Banrisul, Getnet.

## 📞 Contatos e Encaminhamentos
- Troca de Óleo/Dúvidas Unidade: Passar telefone (53) 3241-4056. Avisar: "Se ninguém atender, mande 'Não consegui contato'".
- Comercial (Negociação/Prazos/Frotas): Encaminhar (needs_human=true). (Tel: 53 9943-8244 apenas se insistir muito).
- RH (Currículos): Enviar para vemsergbi@gbirs.com.br
- Reclamações/Sugestões: Enviar para daliane.hahn@gbirs.com.br (ou encaminhar internamente needs_human=true).
- Financeiro (Boletos/Faturas): Encaminhar para setor Financeiro (needs_human=true).

# CLASSIFICAÇÃO DE SETORES E INTENÇÕES (MUITO IMPORTANTE)
Classifique a mensagem do usuário em uma das seguintes intenções:

- contas_pagar: Fornecedores cobrando, envio de notas fiscais, setor financeiro (pagamentos da empresa). "Sou fornecedor e quero enviar a nota".
- compras: Setor de compras, novos fornecedores oferecendo produtos, parcerias. "Quero apresentar meu produto", "Gostaria de ser fornecedor".
- contas_receber: Clientes pedindo boletos, negociação de dívidas, setor de cobrança. "Preciso da segunda via do boleto".
- comercial: Cotação para empresas, parcerias, vendas em grande quantidade (frotas). (NÃO use para preço simples de bomba).
- rh: Envio de currículo, vagas de emprego, "trabalhe conosco". "Quero enviar um currículo".
- atendente: Usuário pede explicitamente para falar com humano, está irritado, diz "falar com atendente", ou tentou ligar e ninguém atendeu ("Não consegui contato").
- geral: Dúvidas comuns (preço da gasolina, horário de funcionamento, endereço, baixar app, reclamações de infraestrutura como calibrador quebrado). O próprio BOT deve tentar responder. "Qual o preço?", "O calibrador está quebrado".

# FORMATO DE RESPOSTA OBRIGATÓRIO (JSON)
Você DEVE responder SEMPRE neste formato JSON exato:
{
    "intent": "contas_pagar|compras|contas_receber|comercial|rh|atendente|geral|outros",
    "needs_human": true|false,
    "response": "Sua resposta aqui...",
    "confidence": 0.0 a 1.0
}

## REGRAS DE ENCAMINHAMENTO (needs_human)
- Se intent for 'atendente', 'contas_pagar', 'compras', 'contas_receber', 'comercial' ou 'rh' -> "needs_human": true. (Exceto se for dúvida muito simples que você saiba responder com certeza, mas antecipe o encaminhamento).
- Se intent for 'geral' -> "needs_human": false (Tente resolver).
- Se o usuário disser "Não consegui contato", marque "intent": "atendente" e "needs_human": true.
"""


class OpenAIService:
    """Cliente para OpenAI API"""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
    
    async def analyze_and_respond(
        self,
        message: str,
        context: List[Dict[str, str]] = None,
        customer_name: Optional[str] = None,
        is_business_hours: bool = True
    ) -> Dict[str, Any]:
        """
        Analisa mensagem do cliente e gera resposta.
        
        Args:
            message: Mensagem do cliente
            context: Histórico de mensagens anteriores
            customer_name: Nome do cliente (se conhecido)
            is_business_hours: Se está em horário comercial
        
        Returns:
            Dict com intent, needs_human, response e confidence
        """
        # Monta mensagens para o chat
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # Adiciona contexto se existir
        if context:
            messages.extend(context)
        
        # Adiciona informações extras no prompt do usuário
        user_prompt = f"Mensagem do cliente: {message}"
        
        if customer_name:
            user_prompt = f"Cliente: {customer_name}\n{user_prompt}"
        
        if not is_business_hours:
            user_prompt += "\n\n[ATENÇÃO: Fora do horário comercial. Informe que o atendimento humano está disponível apenas em horário comercial.]"
        
        messages.append({"role": "user", "content": user_prompt})
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            # Parse da resposta JSON
            content = response.choices[0].message.content
            logger.info(f"OpenAI response: {content}")
            
            result = json.loads(content)
            
            # Valida campos obrigatórios
            if "intent" not in result:
                result["intent"] = "outros"
            if "needs_human" not in result:
                result["needs_human"] = False
            if "response" not in result:
                result["response"] = "Desculpe, não consegui processar sua mensagem. Um atendente irá ajudá-lo em breve."
                result["needs_human"] = True
            if "confidence" not in result:
                result["confidence"] = 0.5
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao parsear JSON da OpenAI: {e}")
            return {
                "intent": "outros",
                "needs_human": True,
                "response": "Desculpe, tive um problema ao processar sua mensagem. Um atendente irá ajudá-lo em breve.",
                "confidence": 0.0
            }
        except Exception as e:
            logger.error(f"Erro na OpenAI API: {e}")
            return {
                "intent": "outros",
                "needs_human": True,
                "response": "Desculpe, estou com dificuldades técnicas. Um atendente irá ajudá-lo em breve.",
                "confidence": 0.0
            }
    
    async def generate_response(
        self,
        prompt: str,
        context: List[Dict[str, str]] = None
    ) -> str:
        """
        Gera resposta simples sem análise de intenção.
        
        Args:
            prompt: Prompt para gerar resposta
            context: Contexto de mensagens anteriores
        
        Returns:
            Texto da resposta
        """
        messages = []
        
        if context:
            messages.extend(context)
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Erro na OpenAI API: {e}")
            return "Desculpe, não consegui processar sua solicitação."


# Instância global
openai_service = OpenAIService()


def get_openai_service() -> OpenAIService:
    """Retorna instância do serviço OpenAI"""
    return openai_service
