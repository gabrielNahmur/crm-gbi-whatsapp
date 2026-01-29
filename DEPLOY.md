# 🚀 Guia de Deploy - AWS Lightsail

## Pré-requisitos

- Conta AWS ativa
- Cartão de crédito cadastrado na AWS

---

## PASSO 1: Criar Servidor no AWS Lightsail

### 1.1. Acesse o Lightsail

1. Entre em [lightsail.aws.amazon.com](https://lightsail.aws.amazon.com)
2. Clique em **"Create instance"** (botão laranja)

### 1.2. Configurações da Instância

| Campo             | Valor                                  |
| ----------------- | -------------------------------------- |
| **Region**        | São Paulo (sa-east-1)                  |
| **Platform**      | Linux/Unix                             |
| **Blueprint**     | Ubuntu 22.04 LTS                       |
| **Instance plan** | $10/mês (1GB RAM) - Mínimo recomendado |
| **Name**          | `crm-gbi-whatsapp`                     |

### 1.3. Clique em "Create instance"

### 1.4. Aguarde 2-3 minutos até o status ficar "Running"

### 1.5. Anote o IP Público

- Aparece na tela do Lightsail (ex: `54.123.45.67`)

---

## PASSO 2: Abrir Portas no Firewall

1. Clique na sua instância
2. Vá na aba **"Networking"**
3. Em "IPv4 Firewall", clique em **"+ Add rule"**
4. Adicione estas regras:

| Application | Protocol | Port |
| ----------- | -------- | ---- |
| Custom      | TCP      | 8002 |
| Custom      | TCP      | 5173 |
| HTTPS       | TCP      | 443  |

---

## PASSO 3: Conectar via SSH

1. Na página da instância, clique em **"Connect using SSH"**
2. Um terminal abrirá no navegador

---

## PASSO 4: Instalar Dependências

Cole estes comandos no terminal SSH (um bloco de cada vez):

```bash
# Atualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER

# Instalar Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Instalar Git
sudo apt install git -y

# Reiniciar para aplicar permissões Docker
sudo reboot
```

**Aguarde 30 segundos e reconecte via SSH.**

---

## PASSO 5: Clonar o Projeto

```bash
# Criar pasta do projeto
mkdir -p ~/apps
cd ~/apps

# Clonar repositório
git clone https://github.com/gabrielNahmur/crm-gbi-whatsapp.git
cd crm-gbi-whatsapp
```

**Se você não tem o projeto no GitHub ainda:**

1. Crie um repositório no GitHub
2. Faça push do projeto local
3. Depois clone no servidor

---

## PASSO 6: Configurar Variáveis de Ambiente

```bash
cd ~/apps/crm-gbi-whatsapp/backend

# Copiar template
cp .env.example .env

# Editar com suas credenciais reais
nano .env
```

**Configure estas variáveis:**

```
DATABASE_URL=postgresql://crm_user:SENHA_SEGURA@postgres:5432/whatsapp_crm
REDIS_URL=redis://redis:6379
OPENAI_API_KEY=sua-chave-openai
TWILIO_ACCOUNT_SID=seu-sid-twilio
TWILIO_AUTH_TOKEN=seu-token-twilio
TWILIO_PHONE_NUMBER=seu-numero-twilio
WEBHOOK_BASE_URL=http://SEU_IP_PUBLICO:8002
```

**Salvar:** `Ctrl+O`, Enter, `Ctrl+X`

---

## PASSO 7: Iniciar com Docker Compose

```bash
cd ~/apps/crm-gbi-whatsapp

# Subir todos os containers
docker-compose up -d --build

# Verificar status
docker-compose ps

# Ver logs
docker-compose logs -f
```

---

## PASSO 8: Criar Usuário Admin

```bash
cd ~/apps/crm-gbi-whatsapp/backend

# Entrar no container
docker-compose exec backend bash

# Rodar script de criação
python create_admin.py

# Sair do container
exit
```

---

## PASSO 9: Testar Acesso

Acesse no navegador:

- **Backend:** `http://SEU_IP:8002/api/health`
- **Frontend:** `http://SEU_IP:5173`

---

## 📱 PASSO 10: Configurar Webhook do Twilio

1. Acesse [console.twilio.com](https://console.twilio.com)
2. Vá em **Messaging > Settings > WhatsApp Sandbox**
3. Configure o webhook: `http://SEU_IP:8002/api/webhooks/twilio`

---

## 🔄 Como Atualizar (Deploy Futuro)

```bash
cd ~/apps/crm-gbi-whatsapp
git pull
docker-compose up -d --build
```

---

## 🆘 Comandos Úteis

```bash
# Ver logs do backend
docker-compose logs -f backend

# Reiniciar tudo
docker-compose restart

# Parar tudo
docker-compose down

# Ver uso de recursos
docker stats
```
