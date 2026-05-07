# 🤖 Bot de Alertas de Preço — Guia de Instalação

## O que você vai precisar
- Computador com Windows, Mac ou Linux
- Python 3.10 ou superior instalado
- Conta no Telegram

---

## PASSO 1 — Criar o seu Bot no Telegram

1. Abra o Telegram e procure por **@BotFather**
2. Envie o comando: `/newbot`
3. Escolha um nome para o bot (ex: `Meu Alerta de Preços`)
4. Escolha um username terminando em `bot` (ex: `meualertabot`)
5. O BotFather vai te dar um **TOKEN** — guarde esse token!
   > Exemplo: `7123456789:AAHdqTcvCHhvQKMUIJbdByTD3GzDmGHKVKo`

---

## PASSO 2 — Instalar o Python

### Windows:
1. Acesse https://python.org/downloads
2. Clique em "Download Python 3.x.x"
3. Instale marcando a opção **"Add Python to PATH"**

### Mac:
```bash
brew install python
```

### Linux (Ubuntu/Debian):
```bash
sudo apt update && sudo apt install python3 python3-pip
```

---

## PASSO 3 — Configurar o bot

### Opção A — Windows (mais fácil):
1. Baixe a pasta `price_bot` para o seu computador
2. Abra o arquivo `bot.py` com o Bloco de Notas ou VS Code
3. Encontre a linha:
   ```python
   TOKEN = os.getenv("TELEGRAM_TOKEN", "SEU_TOKEN_AQUI")
   ```
4. Substitua `SEU_TOKEN_AQUI` pelo token do BotFather:
   ```python
   TOKEN = os.getenv("TELEGRAM_TOKEN", "7123456789:AAHdqTcvCHhvQKMUIJbdByTD3GzDmGHKVKo")
   ```
5. Salve o arquivo

### Opção B — Usando variável de ambiente (mais seguro):

**Windows (PowerShell):**
```powershell
$env:TELEGRAM_TOKEN="SEU_TOKEN_AQUI"
```

**Mac/Linux:**
```bash
export TELEGRAM_TOKEN="SEU_TOKEN_AQUI"
```

---

## PASSO 4 — Instalar as dependências

Abra o terminal (ou Prompt de Comando) dentro da pasta `price_bot` e rode:

```bash
pip install -r requirements.txt
```

---

## PASSO 5 — Rodar o bot

```bash
python bot.py
```

Você vai ver a mensagem:
```
🤖 Bot iniciado! Pressione Ctrl+C para parar.
```

---

## PASSO 6 — Usar o bot

1. Abra o Telegram
2. Procure pelo username do seu bot (ex: `@meualertabot`)
3. Clique em **Start** ou envie `/start`
4. Use os comandos:

| Comando | O que faz |
|---------|-----------|
| `/adicionar` | Adiciona um produto para monitorar |
| `/listar` | Mostra produtos monitorados |
| `/remover` | Remove um produto |
| `/verificar` | Verifica preços agora |
| `/ajuda` | Instruções de uso |

---

## Como adicionar um produto

1. Envie `/adicionar`
2. Cole o link do produto (Amazon BR ou Mercado Livre)
3. O bot detecta o nome e preço atual automaticamente
4. Informe o preço-alvo (ex: `1500.00`)
5. Pronto! Você receberá um alerta quando o preço baixar ✅

---

## Manter o bot rodando 24h (opcional)

Para o bot funcionar mesmo com o computador fechado, você pode usar serviços gratuitos como:

- **Railway.app** — gratuito, fácil de configurar
- **Render.com** — plano gratuito disponível
- **Oracle Cloud** — VM gratuita para sempre

---

## Problemas comuns

### "ModuleNotFoundError"
Rode novamente: `pip install -r requirements.txt`

### Bot não responde
- Confirme que o bot está rodando (terminal aberto)
- Verifique se o TOKEN está correto

### Preço não detectado
- Alguns produtos têm proteção anti-bot
- Tente o link direto do produto (não da busca)
- Funciona melhor com links da Amazon e Mercado Livre

---

## Suporte a sites

| Site | Status |
|------|--------|
| Amazon Brasil (amazon.com.br) | ✅ Suportado |
| Mercado Livre (mercadolivre.com.br) | ✅ Suportado |
| Kabum, Magazine Luiza, etc. | 🔜 Em breve |
