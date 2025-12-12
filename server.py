import asyncio
import json
import uuid
from typing import Any, Dict

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI(title="MCP Streamable HTTP demo")

# Armazena futures para respostas de elicitation
elicitation_futures: Dict[int, asyncio.Future] = {}

# Armazena informações simples de sessão, só para demonstração
session_store: Dict[str, Dict[str, Any]] = {}


def make_sse_event(payload: Dict[str, Any]) -> bytes:
    """
    Converte um dict em um evento SSE simples no formato:

    data: {"jsonrpc": "...", ...}

    (seguido de linha em branco)
    """
    data = json.dumps(payload, ensure_ascii=False)
    text = f"data: {data}\n\n"
    return text.encode("utf-8")


@app.post("/mcp")
async def mcp_post(request: Request):
    """
    Endpoint principal MCP (Streamable HTTP).

    - Sempre recebe JSON (um único objeto).
    - Se tiver "method": tratamos como request ou notification.
    - Se tiver "id" e "result" (sem "method"): tratamos como response (por exemplo, de elicitation).
    """
    body = await request.json()

    if isinstance(body, list):
        # Para simplificar, não suportamos batch neste demo
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32600,
                    "message": "Batch requests are not supported in this demo"
                },
            },
            status_code=400,
        )

    method = body.get("method")

    # Requests / notifications
    if method is not None:
        if method == "initialize":
            return await handle_initialize(body)

        if method == "notifications/initialized":
            # Notification simples: retornamos 202 Accepted sem corpo
            return Response(status_code=202)

        if method == "tools/list":
            return await handle_tools_list(body)

        if method == "tools/call":
            return await handle_tools_call(body)

        if method == "resources/list":
            return await handle_resources_list(body)

        if method == "resources/read":
            return await handle_resources_read(body)

        # Método desconhecido
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                },
            },
            status_code=200,
        )

    # Responses (por exemplo, respostas de elicitation)
    msg_id = body.get("id")
    if msg_id is not None and msg_id in elicitation_futures:
        fut = elicitation_futures[msg_id]
        if not fut.done():
            fut.set_result(body.get("result"))

    # Requests contendo apenas responses/notifications retornam 202 Accepted
    return Response(status_code=202)


async def handle_initialize(msg: Dict[str, Any]) -> JSONResponse:
    """
    Trata o método initialize.
    Cria uma sessão e devolve capabilities básicas.
    """
    session_id = str(uuid.uuid4())
    session_store[session_id] = {}

    response_body = {
        "jsonrpc": "2.0",
        "id": msg.get("id"),
        "result": {
            "protocolVersion": "2025-03-26",
            "capabilities": {
                "logging": {},
                "prompts": {"listChanged": True},
                "resources": {"subscribe": True, "listChanged": True},
                "tools": {"listChanged": True},
            },
            "serverInfo": {
                "name": "ExampleServer",
                "version": "1.0.0",
            },
            "instructions": "Use the tools and resources to help the user.",
        },
    }

    headers = {"Mcp-Session-Id": session_id}
    return JSONResponse(response_body, headers=headers)


async def handle_tools_list(msg: Dict[str, Any]) -> JSONResponse:
    """
    Lista duas tools:
    - get_weather
    - register_user (que usa elicitation)
    """
    response_body = {
        "jsonrpc": "2.0",
        "id": msg.get("id"),
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
                                "description": "City name or zip code",
                            },
                            "forecastDays": {
                                "type": "integer",
                                "description": "Number of days for forecast (optional)",
                            },
                        },
                        "required": ["location"],
                    },
                },
                {
                    "name": "register_user",
                    "description": "Register a user using elicitation to collect profile data",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "useElicitation": {
                                "type": "boolean",
                                "description": "If true, server will ask user for details using elicitation",
                            }
                        },
                        "required": ["useElicitation"],
                    },
                },
            ],
            "nextCursor": None,
        },
    }
    return JSONResponse(response_body)


async def handle_tools_call(msg: Dict[str, Any]):
    """
    Trata tools/call para:
    - get_weather (normal e streaming)
    - register_user (com elicitation)
    """
    params = msg.get("params") or {}
    name = params.get("name")
    arguments = params.get("arguments") or {}

    if name == "get_weather":
        return await handle_get_weather(msg, arguments)

    if name == "register_user":
        return await handle_register_user(msg, arguments)

    # Tool não encontrada
    response_body = {
        "jsonrpc": "2.0",
        "id": msg.get("id"),
        "error": {
            "code": -32601,
            "message": f"Tool not found: {name}",
        },
    }
    return JSONResponse(response_body, status_code=200)


async def handle_get_weather(msg: Dict[str, Any], arguments: Dict[str, Any]):
    """
    Implementação da tool get_weather.
    - Se forecastDays não é enviado: resposta HTTP normal (JSON único).
    - Se forecastDays é enviado: resposta em streaming SSE.
    """
    location = arguments.get("location", "Unknown")
    forecast_days = arguments.get("forecastDays")

    if forecast_days is None:
        # Resposta simples, sem streaming
        content_text = (
            f"Current weather in {location}:\n"
            "Temperature: 25°C\n"
            "Conditions: Clear sky"
        )
        response_body = {
            "jsonrpc": "2.0",
            "id": msg.get("id"),
            "result": {
                "content": [
                    {"type": "text", "text": content_text}
                ],
                "isError": False,
            },
        }
        return JSONResponse(response_body)

    # Resposta em streaming SSE
    async def event_gen():
        log_msg = {
            "jsonrpc": "2.0",
            "method": "notifications/log",
            "params": {
                "level": "info",
                "message": f"Starting {forecast_days}-day forecast for {location}",
                "timestamp": "2025-12-11T00:00:00Z",
            },
        }
        yield make_sse_event(log_msg)
        await asyncio.sleep(0.5)

        forecast_lines = []
        for day in range(1, int(forecast_days) + 1):
            forecast_lines.append(f"Day {day}: 25°C, clear")

        content_text = (
            f"{forecast_days}-day forecast for {location}:\n"
            + "\n".join(forecast_lines)
        )
        result_msg = {
            "jsonrpc": "2.0",
            "id": msg.get("id"),
            "result": {
                "content": [
                    {"type": "text", "text": content_text}
                ],
                "isError": False,
            },
        }
        yield make_sse_event(result_msg)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


async def handle_register_user(msg: Dict[str, Any], arguments: Dict[str, Any]):
    """
    Implementação da tool register_user com elicitation.
    """
    use_elicitation = arguments.get("useElicitation", False)
    if not use_elicitation:
        response_body = {
            "jsonrpc": "2.0",
            "id": msg.get("id"),
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": "useElicitation must be true in this demo",
                    }
                ],
                "isError": True,
            },
        }
        return JSONResponse(response_body, status_code=200)

    call_id = msg.get("id")

    async def event_gen_register():
        elic_id = 100
        loop = asyncio.get_event_loop()
        fut: asyncio.Future = loop.create_future()
        elicitation_futures[elic_id] = fut

        # Primeiro, o servidor cria uma elicitation
        create_msg = {
            "jsonrpc": "2.0",
            "id": elic_id,
            "method": "elicitation/create",
            "params": {
                "message": "Please provide your registration data",
                "requestedSchema": {
                    "type": "object",
                    "properties": {
                        "fullName": {
                            "type": "string",
                            "description": "Your full name",
                        },
                        "email": {
                            "type": "string",
                            "format": "email",
                            "description": "Your email address",
                        },
                        "acceptTerms": {
                            "type": "boolean",
                            "description": "Do you accept our terms of service",
                        },
                    },
                    "required": ["fullName", "email", "acceptTerms"],
                },
            },
        }
        yield make_sse_event(create_msg)

        # Espera o client responder a elicitation
        result = await fut

        full_name = result["content"]["fullName"]
        email = result["content"]["email"]
        accept_terms = result["content"]["acceptTerms"]

        text = (
            "User registered successfully:\n"
            f"Name: {full_name}\n"
            f"Email: {email}\n"
            f"Accepted terms: {accept_terms}"
        )

        final_msg = {
            "jsonrpc": "2.0",
            "id": call_id,
            "result": {
                "content": [
                    {"type": "text", "text": text}
                ],
                "isError": False,
            },
        }
        yield make_sse_event(final_msg)

        # Limpa a future da elicitation
        del elicitation_futures[elic_id]

    return StreamingResponse(event_gen_register(), media_type="text/event-stream")


async def handle_resources_list(msg: Dict[str, Any]) -> JSONResponse:
    """
    Lista um resource simples: resource://docs/terms.
    """
    response_body = {
        "jsonrpc": "2.0",
        "id": msg.get("id"),
        "result": {
            "resources": [
                {
                    "uri": "resource://docs/terms",
                    "name": "Terms of Service",
                    "description": "Human readable terms of service",
                    "mimeType": "text/markdown",
                }
            ],
            "nextCursor": None,
        },
    }
    return JSONResponse(response_body)


async def handle_resources_read(msg: Dict[str, Any]) -> JSONResponse:
    """
    Lê o conteúdo de resource://docs/terms.
    """
    params = msg.get("params") or {}
    uri = params.get("uri")

    if uri != "resource://docs/terms":
        response_body = {
            "jsonrpc": "2.0",
            "id": msg.get("id"),
            "error": {
                "code": -32602,
                "message": f"Unknown resource URI: {uri}",
            },
        }
        return JSONResponse(response_body, status_code=200)

    text = "# Terms of Service\n\nYou agree to use this service responsibly."
    response_body = {
        "jsonrpc": "2.0",
        "id": msg.get("id"),
        "result": {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "text/markdown",
                    "text": text,
                }
            ]
        },
    }
    return JSONResponse(response_body)


@app.get("/mcp")
async def mcp_get(request: Request):
    """
    Endpoint GET /mcp usado para notificações assíncronas via SSE.
    """
    async def gen():
        notif1 = {
            "jsonrpc": "2.0",
            "method": "notifications/tools/list_changed",
        }
        yield make_sse_event(notif1)
        await asyncio.sleep(1.0)
        notif2 = {
            "jsonrpc": "2.0",
            "method": "notifications/resources/list_changed",
        }
        yield make_sse_event(notif2)

    return StreamingResponse(gen(), media_type="text/event-stream")


def main():
    import uvicorn

    uvicorn.run(
        "server:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
