# MCP Streamable HTTP Demo (Python)

Projeto completo em Python demonstrando **Streamable HTTP + SSE** para MCP, com:

- Servidor MCP (`server.py`) implementado com FastAPI.
- Cliente MCP (`client.py`) usando `httpx`.
- Workflows cobrindo:
  - `initialize` e `notifications/initialized`
  - `tools/list`
  - `tools/call` com resposta HTTP normal
  - `tools/call` com resposta em streaming SSE
  - `resources/list` e `resources/read`
  - Notificações assíncronas via `GET /mcp` (SSE)
  - Tool com **elicitation** (`register_user`), incluindo:
    - `elicitation/create`
    - Resposta do cliente à elicitation
    - Resultado final da tool

O objetivo é ter o **HTTP inteiro**, do protocolo mostrando cada passo do protocolo MCP.

Para maiores detalhes sobre MCP consulte a documentação oficial em:

https://modelcontextprotocol.io/specification/2025-11-25

---

## 0. Requisitos

- Python 3.10 ou superior
- [uv](https://docs.astral.sh/uv/) instalado globalmente

---

## 1. Como instalar

No diretório do projeto:

```bash
uv venv
uv sync
```

Isso vai criar o ambiente virtual e instalar as dependências:

- `fastapi` (servidor web)
- `uvicorn[standard]` (servidor ASGI)
- `httpx` (cliente HTTP assíncrono)
- `rich` (para saída colorida no console)


---

## 2. Como rodar o servidor

No diretório do projeto:

```bash
uv run server.py
```

O servidor sobe em:

```text
http://127.0.0.1:8000
```

O endpoint MCP é:

```text
POST /mcp
ou
GET  /mcp
```

---

## 3. Como rodar o cliente

Em outro terminal, também no diretório do projeto:

```bash
uv run client.py
```

Ele executa, em sequência:

1. `initialize`
2. `notifications/initialized`
3. `tools/list`
4. `tools/call get_weather` (resposta normal JSON)
5. `tools/call get_weather` (streaming SSE)
6. `resources/list`
7. `resources/read resource://docs/terms`
8. `GET /mcp` para receber notificações SSE
9. `tools/call register_user` com elicitation

O cliente imprime tudo no terminal: requests, respostas, status HTTP e mensagens SSE.

---
## 4. HTTP, SSE, JSON-RPC, HTTP Stremable e MCP

Antes de ver os detalhes dos workflows, é importante entender como o MCP Streamable HTTP funciona, e como ele usa HTTP, JSON-RPC e SSE.

Vamos entender os conceitos básicos de conexão TCP/IP e o modelo OSI, bem como o conceito de cliente-servidor e como os protocolos de aplicação funcionam (que logo mais veremos que reside na camada 7 do modelo OSI).

### 4.1 Camadas de rede: OSI, TCP/IP e onde o HTTP entra

Quando a gente fala de conexão, na prática estamos lidando com camadas de abstração.

Não precisa decorar o modelo OSI, mas ter a imagem na cabeça ajuda:

* Camadas mais baixas (físico, enlace, rede)
→ cabo, wi-fi, IP, roteador, etc. Como desenvolvedores não vamos mexer aqui.

* Camada de transporte (TCP)
→ garante que os bytes chegam na ordem.

* Camada de aplicação (HTTP, WebSocket, etc.)
→ define o “protocolo de conversa” entre cliente e servidor.

Um jeito bem simplificado de pensar:

TCP é um cano contínuo de bytes entre cliente e servidor e HTTP é uma convenção em cima desse cano que vai combinar o jogo sobre como os bytes são organizados em mensagens tais como padrões sobre o começo da requisição (POST /mcp HTTP/1.1) headers (Content-Type, Accept, etc.) corpo (que pode ser JSON, HTML, SSE, o que a gente quiser).

Em cima de HTTP, a gente ainda pode ter outro protocolo, como JSON-RPC que define o formato de mensagens (method, params, result, error) e se aplica mais especificamente no corpo, matendo headers e outros detalhes já definidos no HTTP.

O MCP define quais métodos existem (initialize, tools/call, etc.) e o que eles significam, visto que o JSON-RPC é só um formato genérico sem combinar significados específicos.

Então o modelo mental que temos é:

```
MCP        → "quais métodos existem" (initialize, tools/call, resources/read…)
JSON-RPC   → "como é o formato das mensagens" (jsonrpc, id, method, result…)
HTTP       → "como cliente e servidor trocam requisições e respostas"
TCP        → "canduíte confiável de bytes"
```

### 4.2 Modelo cliente-servidor e HTTP "normal"

No modelo clássico cliente-servidor, o cliente abre uma conexão TCP com o servidor e em cima dessa conexão, ele manda uma requisição HTTP, com um formato mais ou menos assim:

uma linha de início:
POST /mcp HTTP/1.1

alguns headers:
Host, Content-Type, Accept, Mcp-Session-Id, etc.

um corpo (body), que no nosso caso é JSON com JSON-RPC dentro.

Exemplo (modo não-streaming):

```
POST /mcp HTTP/1.1
Host: exemplo.com
Content-Type: application/json
Accept: application/json, text/event-stream

{"jsonrpc":"2.0","id":1,"method":"initialize","params":{...}}
```

O servidor então lê isso tudo e processa a lógica e devolve uma resposta HTTP, que tem o formato:

```
HTTP/1.1 200 OK
Content-Type: application/json

{"jsonrpc":"2.0","id":1,"result":{...}}
```

Existem algumas regras simples no HTTP "normal":

1 requisição → 1 resposta.

E a resposta tem:

a) status (200 OK, 404, etc.)

b) headers

c) e um corpo (que pode ser JSON, HTML, etc.).

Depois que o corpo terminou, acabou essa resposta e isso é o "modo simples" ou "normal" do HTTP: requisição, resposta, fim.

### 4.3 Onde entra o JSON-RPC nessa história

O corpo da requisição/resposta HTTP, pra gente, é sempre um JSON com o formato do JSON-RPC. P.ex.:

Requisição:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "get_weather",
    "arguments": {
      "location": "São Paulo"
    }
  }
}
```

Resposta:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      { "type": "text", "text": "Current weather in São Paulo: ..." }
    ],
    "isError": false
  }
}
```
Ideia geral aqui é:

- O HTTP define: "tem um corpo aqui".
- O JSON define: "esse corpo segue o padrão JavaScript Object Notation".
- O JSON-RPC define: "esse corpo é json com uma mensagem com método X, parâmetros Y, id Z".

O MCP então pega o JSON-RPC e diz:

method = "initialize" → significa “vamos negociar versão, capabilities, etc.”

method = "tools/list" → significa “me diga quais ferramentas você expõe”.

method = "tools/call" → significa “chama essa tool com esses argumentos”.

etc.

Ou seja: HTTP é a estrutura, JSON é o formato, JSON-RPC é a linguagem, MCP é o vocabulário. Não é a melhor analogia do mundo, mas ajuda a entender hahaha.

### 4.4 Onde entra SSE: HTTP em "modo streaming"

Agora vem o SSE (Server-Sent Events). Em linguagem simples, SSE é um padrão HTTP que permite ao servidor enviar múltiplos eventos para o cliente em uma única conexão HTTP aberta.

Sem SSE (modo normal), o fluxo é:

Requisição:

```
POST /mcp HTTP/1.1
Host: exemplo.com
Content-Type: application/json
Accept: application/json, text/event-stream

{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{...}}
```

Resposta:

```
HTTP/1.1 200 OK
Content-Type: application/json

{"jsonrpc":"2.0","id":4,"result":{...}}
```

Com SSE (modo streaming), o fluxo é:
Requisição:

```
POST /mcp HTTP/1.1
Host: exemplo.com
Content-Type: application/json
Accept: application/json, text/event-stream
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{...}}
```

Resposta:

```
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive

data: { "jsonrpc": "2.0", "method": "notifications/log", ... }

data: { "jsonrpc": "2.0", "id": 4, "result": { ... } }
```


Detalhes importantes:

O cabeçalho HTTP (HTTP 200, Content-Type, etc.) vem uma vez só, no começo. Já o corpo é um texto contínuo onde cada evento vem em uma ou mais linhas começando com data: ...

Uma linha em branco separa um evento do próximo e a conexão fica aberta permintindo o servidor enviar um data: ... agora, depois de 1s envia outro data: ..., depois de 5s outro… etc...O cliente pode ficar lendo isso como se fosse um chat.

O SSE, portanto, não é outro protocolo de rede, é só um jeito de usar HTTP para mandar múltiplas mensagens em sequência. É um jeito padronizado de escrever texto dentro de uma resposta HTTP. O conteúdo do data é totalmente livre, pode ser data: "olá", data: {meu JSON}, um CSV, tanto faz.

### 4.5 Como o MCP usa HTTP + JSON-RPC + SSE (Streamable HTTP)

Agora com as peças isoladas já esclarecidas, dá pra ver o MCP Streamable HTTP como uma combinação de tudo isso:

* TCP: conexão confiável de bytes.

* HTTP: cliente faz POST /mcp e opcionalmente GET /mcp.

* Servidor: responde com application/json ou text/event-stream.

* SSE: (só quando é streaming)

* Se o servidor escolher Content-Type: text/event-stream, começa a mandar:
```
  data: { ...json-rpc... }
  linha em branco
  data: { ...json-rpc... }
  linha em branco
  e assim por diante.
```
* JSON-RPC: cada data: ... carrega um objeto JSON-RPC completo e existe um campo id que liga request ↔ response equanto que o method identifica notificações, elicitation, etc.

* MCP: define quais métodos existem e como usar: initialize, tools/list, tools/call, resources/read, elicitation/create, notifications/... etc. O MCP também define o comportamento do transporte.
* Streamable HTTP: sempre POST /mcp com JSON. O server pode responder com JSON único (não streaming), ou abrir um stream SSE com 1 ou vários JSON-RPC (data: ...).

### 4.6 O que mudou do MCP antigo para o MCP Streamable HTTP

O MCP original usava SSE como transporte primário, com GET /sse para abrir o stream e POST /messages para mandar requests.

No modelo antigo funcionava assim:

GET /sse abre o stream, POST /messages manda requests, e as respostas chegavam só pelo /sse.

Agora, com Streamable HTTP funciona assim:

POST /mcp já é suficiente pra mandar o request e receber a resposta. que pode ser um JSON único, ou um stream SSE (data: ... data: ...), no mesmo endpoint.

Ou seja:

O que foi deprecado foi o transporte antigo (GET /sse + POST /messages). O SSE em si continua normal, mas agora como "modo streaming de resposta do /mcp" e não mais como transporte separado.

Com isso em mente, quando você olhar o código do server.py e do client.py, fica bem mais fácil enxergar quando é HTTP normal e quando é SSE e quando é JSON-RPC e como o MCP junta tudo isso num fluxo só.

---

## 5. HTTP MCP (Streamable HTTP + SSE)

Abaixo está uma descrição dos principais workflows cobertos pelo demo, mas usando HTTP puro.

### 5.1 Inicialização da sessão (initialize + initialized)

#### 5.1.1 Cliente → Servidor: `initialize` via `POST /mcp`

```http
POST /mcp HTTP/1.1
Host: api.exemplo.com
Content-Type: application/json
Accept: application/json, text/event-stream

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-03-26",
    "capabilities": {
      "roots": {
        "listChanged": true
      },
      "sampling": {},
      "elicitation": {}
    },
    "clientInfo": {
      "name": "ExampleClient",
      "version": "1.0.0"
    }
  }
}
```

#### 5.1.2 Servidor → Cliente: resposta JSON com capabilities e sessão

```http
HTTP/1.1 200 OK
Content-Type: application/json
Mcp-Session-Id: 2f61f1d3-97b8-4b62-9e85-8ce9f3b9f111

{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2025-03-26",
    "capabilities": {
      "logging": {},
      "prompts": {
        "listChanged": true
      },
      "resources": {
        "subscribe": true,
        "listChanged": true
      },
      "tools": {
        "listChanged": true
      }
    },
    "serverInfo": {
      "name": "ExampleServer",
      "version": "1.0.0"
    },
    "instructions": "Use the tools and resources to help the user."
  }
}
```

#### 5.1.3 Cliente → Servidor: `notifications/initialized`

```http
POST /mcp HTTP/1.1
Host: api.exemplo.com
Content-Type: application/json
Accept: application/json, text/event-stream
Mcp-Session-Id: 2f61f1d3-97b8-4b62-9e85-8ce9f3b9f111

{
  "jsonrpc": "2.0",
  "method": "notifications/initialized"
}
```

Resposta do servidor:

```http
HTTP/1.1 202 Accepted
Content-Length: 0
```

Esse fluxo é o mesmo implementado em `client.initialize()` e `client.send_initialized_notification()`.

---

### 5.2 Chamada simples de tool, resposta HTTP normal (sem streaming)

#### 5.2.1 Cliente → Servidor: listar tools (`tools/list`)

```http
POST /mcp HTTP/1.1
Host: api.exemplo.com
Content-Type: application/json
Accept: application/json, text/event-stream
Mcp-Session-Id: 2f61f1d3-97b8-4b62-9e85-8ce9f3b9f111

{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {
    "cursor": null
  }
}
```

#### 5.2.2 Servidor → Cliente: lista de tools

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      {
        "name": "get_weather",
        "description": "Get current weather information for a location",
        "inputSchema": {
          "type": "object",
          "properties": {
            "location": {
              "type": "string",
              "description": "City name or zip code"
            }
          },
          "required": ["location"]
        }
      },
      {
        "name": "register_user",
        "description": "Register a user using elicitation to collect profile data",
        "inputSchema": {
          "type": "object",
          "properties": {
            "useElicitation": {
              "type": "boolean",
              "description": "If true, server will ask user for details using elicitation"
            }
          },
          "required": ["useElicitation"]
        }
      }
    ],
    "nextCursor": null
  }
}
```

#### 5.2.3 Cliente → Servidor: chamar `get_weather` (resposta não streaming)

```http
POST /mcp HTTP/1.1
Host: api.exemplo.com
Content-Type: application/json
Accept: application/json, text/event-stream
Mcp-Session-Id: 2f61f1d3-97b8-4b62-9e85-8ce9f3b9f111

{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "get_weather",
    "arguments": {
      "location": "São Paulo"
    }
  }
}
```

#### 5.2.4 Servidor → Cliente: resposta JSON única

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Current weather in São Paulo:\nTemperature: 25°C\nConditions: Clear sky"
      }
    ],
    "isError": false
  }
}
```

---

### 5.3 Chamada de tool com resposta via SSE (Streamable HTTP)

Agora o servidor usa SSE como forma de resposta.

#### 5.3.1 Cliente → Servidor: `get_weather` com forecast

```http
POST /mcp HTTP/1.1
Host: api.exemplo.com
Content-Type: application/json
Accept: application/json, text/event-stream
Mcp-Session-Id: 2f61f1d3-97b8-4b62-9e85-8ce9f3b9f111

{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "get_weather",
    "arguments": {
      "location": "São Paulo",
      "forecastDays": 5
    }
  }
}
```

#### 5.3.2 Servidor → Cliente: resposta SSE com vários eventos

```http
HTTP/1.1 200 OK
Content-Type: text/event-stream

data: {"jsonrpc":"2.0","method":"notifications/log","params":{"level":"info","message":"Starting 5-day forecast for São Paulo","timestamp":"2025-12-11T00:00:00Z"}}

data: {"jsonrpc":"2.0","id":4,"result":{"content":[{"type":"text","text":"5-day forecast for São Paulo:\nDay 1: 25°C, clear\nDay 2: 24°C, clear\nDay 3: 26°C, clear\nDay 4: 27°C, clear\nDay 5: 28°C, clear"}],"isError":false}}
```

Cada bloco `data: ...` é um evento SSE. O cliente MCP lê linha por linha, extrai o JSON depois de `data:` e trata como mensagem JSON-RPC normal.

No código, esse fluxo está em `client.call_get_weather_streaming()` e `server.handle_get_weather()`.

---

### 5.4 Workflows de Resources: listar e ler resource

#### 5.4.1 Cliente → Servidor: listar resources (`resources/list`)

```http
POST /mcp HTTP/1.1
Host: api.exemplo.com
Content-Type: application/json
Accept: application/json, text/event-stream
Mcp-Session-Id: 2f61f1d3-97b8-4b62-9e85-8ce9f3b9f111

{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "resources/list",
  "params": {
    "cursor": null
  }
}
```

#### 5.4.2 Servidor → Cliente: lista de resources

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 5,
  "result": {
    "resources": [
      {
        "uri": "resource://docs/terms",
        "name": "Terms of Service",
        "description": "Human readable terms of service",
        "mimeType": "text/markdown"
      }
    ],
    "nextCursor": null
  }
}
```

#### 5.4.3 Cliente → Servidor: ler `resource://docs/terms` (`resources/read`)

```http
POST /mcp HTTP/1.1
Host: api.exemplo.com
Content-Type: application/json
Accept: application/json, text/event-stream
Mcp-Session-Id: 2f61f1d3-97b8-4b62-9e85-8ce9f3b9f111

{
  "jsonrpc": "2.0",
  "id": 6,
  "method": "resources/read",
  "params": {
    "uri": "resource://docs/terms"
  }
}
```

#### 5.4.4 Servidor → Cliente: conteúdo do resource

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 6,
  "result": {
    "contents": [
      {
        "uri": "resource://docs/terms",
        "mimeType": "text/markdown",
        "text": "# Terms of Service\n\nYou agree to use this service responsibly."
      }
    ]
  }
}
```

---

### 5.5 Notificações assíncronas via `GET /mcp` (SSE)

O servidor pode mandar notificações fora do contexto de uma requisição específica, usando um stream SSE aberto via `GET`.

#### 5.5.1 Cliente → Servidor: abrir `GET /mcp` com `Accept: text/event-stream`

```http
GET /mcp HTTP/1.1
Host: api.exemplo.com
Accept: text/event-stream
Mcp-Session-Id: 2f61f1d3-97b8-4b62-9e85-8ce9f3b9f111
```

#### 5.5.2 Servidor → Cliente: stream SSE com notificações

```http
HTTP/1.1 200 OK
Content-Type: text/event-stream

data: {"jsonrpc":"2.0","method":"notifications/tools/list_changed"}

data: {"jsonrpc":"2.0","method":"notifications/resources/list_changed"}
```

No demo, isso é implementado em `server.mcp_get()` e consumido em `client.listen_notifications_via_get()`.

---

### 5.6 Workflow completo com Elicitation durante uma tool call

#### Tool usada

- `register_user`
- Intenção: registrar um usuário, mas coletando dados via elicitation.

#### 5.6.1 Cliente → Servidor: chamar `register_user` com `useElicitation: true`

```http
POST /mcp HTTP/1.1
Host: api.exemplo.com
Content-Type: application/json
Accept: application/json, text/event-stream
Mcp-Session-Id: 2f61f1d3-97b8-4b62-9e85-8ce9f3b9f111

{
  "jsonrpc": "2.0",
  "id": 10,
  "method": "tools/call",
  "params": {
    "name": "register_user",
    "arguments": {
      "useElicitation": true
    }
  }
}
```

#### 5.6.2 Servidor → Cliente: abre SSE e envia `elicitation/create`

```http
HTTP/1.1 200 OK
Content-Type: text/event-stream

data: {
  "jsonrpc": "2.0",
  "id": 100,
  "method": "elicitation/create",
  "params": {
    "message": "Please provide your registration data",
    "requestedSchema": {
      "type": "object",
      "properties": {
        "fullName": {
          "type": "string",
          "description": "Your full name"
        },
        "email": {
          "type": "string",
          "format": "email",
          "description": "Your email address"
        },
        "acceptTerms": {
          "type": "boolean",
          "description": "Do you accept our terms of service"
        }
      },
      "required": ["fullName", "email", "acceptTerms"]
    }
  }
}
```

No demo, o servidor cria uma `Future` para `id` 100 e fica esperando a resposta.

#### 5.6.3 Cliente → Servidor: resposta à elicitation via novo `POST /mcp`

```http
POST /mcp HTTP/1.1
Host: api.exemplo.com
Content-Type: application/json
Accept: application/json, text/event-stream
Mcp-Session-Id: 2f61f1d3-97b8-4b62-9e85-8ce9f3b9f111

{
  "jsonrpc": "2.0",
  "id": 100,
  "result": {
    "action": "accept",
    "content": {
      "fullName": "Willams Sousa",
      "email": "willams@example.com",
      "acceptTerms": true
    }
  }
}
```

Resposta HTTP do servidor:

```http
HTTP/1.1 202 Accepted
Content-Length: 0
```

No código do cliente (`_respond_to_elicitation`), essa resposta é enviada de forma automática, sem pedir input.

#### 5.6.4 Servidor → Cliente: resultado final da tool `register_user` pelo mesmo stream SSE

```http
data: {
  "jsonrpc": "2.0",
  "id": 10,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "User registered successfully:\nName: Willams Sousa\nEmail: willams@example.com\nAccepted terms: true"
      }
    ],
    "isError": false
  }
}
```

Quando o cliente vê uma mensagem SSE com `id: 10` e `result`, ele encerra o fluxo dessa chamada.

---

## 6. Resumo

- Todo tráfego cliente → servidor passa por `POST /mcp` com JSON no corpo.
- O servidor escolhe se responde:
  - com JSON único (`Content-Type: application/json`); ou
  - com stream SSE (`Content-Type: text/event-stream`) contendo vários eventos `data: {...}`.
- Requests que só contêm notifications ou responses retornam `202 Accepted` sem corpo.
- Para receber notificações assíncronas, o cliente abre um `GET /mcp` com `Accept: text/event-stream`.
- Elicitation é só mais um request JSON-RPC vindo do servidor, que o cliente responde com outro `POST /mcp`.

O código deste projeto implementa tudo isso de forma mínima, mas completa.

Estude o código do servidor.
Estude o código do cliente.
Veja as sequências de HTTP e SSE no console.
Ajuste, brinque, adicione ferramentas e recursos novos, e experimente com o protocolo MCP Streamable HTTP em um ambiente controlado.

Bom estudo e happy coding!
