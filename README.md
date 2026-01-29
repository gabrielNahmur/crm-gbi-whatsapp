# WhatsApp CRM - Sistema de Atendimento GBI

Sistema de CRM e atendimento via WhatsApp com chatbot inteligente usando OpenAI GPT-4.

## 🚀 Funcionalidades

- ✅ **Chatbot com IA** - Identifica intenções e responde automaticamente
- ✅ **Dashboard de Atendimento** - Interface web moderna para atendentes
- ✅ **Filas por Setor** - Comercial, Compras, Contas a Pagar, Contas a Receber, RH
- ✅ **Fila de Atendimento Humano** - Visível para todos os setores
- ✅ **Histórico de Conversas** - Contexto preservado para melhor atendimento
- ✅ **Respostas Automáticas** - Fora do horário comercial
- ✅ **WebSocket** - Atualizações em tempo real
- ✅ **Docker Ready** - Deploy com docker-compose

## 📋 Setores Configurados

| Setor                  | Descrição                             |
| ---------------------- | ------------------------------------- |
| **Comercial**          | Cotações, frotas, vendas corporativas |
| **Compras**            | Novos fornecedores, parcerias         |
| **Contas a Pagar**     | Fornecedores com NF, cobranças        |
| **Contas a Receber**   | Clientes pedindo boletos, negociação  |
| **RH**                 | Currículos, vagas de emprego          |
| **Atendimento Humano** | Escalações - Visível para todos       |
| **Geral**              | Dúvidas simples (Bot resolve)         |

## 🛠️ Instalação Rápida (Docker)

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/pipeline-CRM.git
cd pipeline-CRM

# 2. Configure as variáveis de ambiente
cp .env.production .env
nano .env  # Preencha suas credenciais

# 3. Suba os containers
docker compose up -d --build

# 4. Acesse
http://localhost
```

## 🛠️ Instalação Local (Desenvolvimento)

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
cp .env.example .env   # Configure suas credenciais
uvicorn app.main:app --reload --port 8002
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## 🔧 Configuração do Twilio WhatsApp

1. Acesse [twilio.com/console](https://www.twilio.com/console)
2. Vá em **Messaging > WhatsApp Sandbox**
3. Configure o Webhook: `https://seu-dominio.com/api/webhook/twilio`
4. Copie Account SID e Auth Token para o `.env`

## 🔑 Variáveis de Ambiente

```env
# Banco de Dados (Docker configura automaticamente)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/whatsapp_crm
REDIS_URL=redis://localhost:6379/0

# Segurança
SECRET_KEY=gere-com-openssl-rand-hex-32

# OpenAI
OPENAI_API_KEY=sk-sua-chave
OPENAI_MODEL=gpt-4o-mini

# Twilio WhatsApp
TWILIO_ACCOUNT_SID=ACxxx
TWILIO_AUTH_TOKEN=xxx
TWILIO_WHATSAPP_NUMBER=+14155238886
USE_TWILIO=true
```

## 📁 Estrutura do Projeto

```
pipeline-CRM/
├── backend/
│   ├── app/
│   │   ├── api/routes/      # Endpoints da API
│   │   ├── database/        # PostgreSQL e Redis
│   │   ├── models/          # SQLAlchemy Models
│   │   ├── services/        # Bot, OpenAI, Twilio
│   │   └── main.py          # FastAPI App
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/pages/           # React Components
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml       # Orquestração
├── DEPLOY.md                # Guia de Deploy VPS
└── README.md
```

## 📝 API Endpoints

### Autenticação

- `POST /api/auth/login` - Login
- `GET /api/auth/me` - Usuário logado

### Conversas

- `GET /api/conversations` - Listar
- `GET /api/conversations/queue` - Fila de espera
- `POST /api/conversations/{id}/accept` - Aceitar
- `POST /api/conversations/{id}/resolve` - Resolver

### Mensagens

- `GET /api/messages/conversation/{id}` - Histórico
- `POST /api/messages/send` - Enviar

### WebSocket

- `ws://host/ws/{agent_id}/{sector}` - Real-time

## 🚀 Deploy em Produção

Consulte o arquivo [DEPLOY.md](./DEPLOY.md) para instruções completas de implantação em VPS (DigitalOcean, AWS Lightsail, etc).

## 📄 Licença

MIT License - GBI Combustíveis
