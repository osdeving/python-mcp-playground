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

Vamos entender os conceitos básicos de conexão TCP/IP e o modelo OSI, bem como o conseito de cliente-servidor e como os protocolos de aplicação funciona (a camada 7 do modelo OSI).

### 4.1 Camadas de rede: OSI, TCP/IP e onde o HTTP entra

Quando a gente fala de conexão, na prática estamos lidando com camadas de abstração. O modelo OSI tem 7 camadas (do físico até a aplicação).

etc... [ TODO: criar essa seção]


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
