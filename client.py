import json
from typing import Any, Dict, Optional

import httpx
from rich.console import Console
from rich.panel import Panel
from rich import print as rprint

console = Console()


class MCPClient:
    """
    Cliente MCP muito simples, falando com o servidor via Streamable HTTP.

    Demonstra na prática:

    - initialize + notifications/initialized
    - tools/list
    - tools/call (resposta normal)
    - tools/call (streaming SSE)
    - resources/list
    - resources/read
    - notificações assíncronas via GET /mcp (SSE)
    - tools/call register_user com elicitation
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8000/mcp") -> None:
        self.base_url = base_url
        self.client = httpx.Client(timeout=None)
        self.session_id: Optional[str] = None
        self._next_id = 1

    def _new_id(self) -> int:
        current = self._next_id
        self._next_id += 1
        return current

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        return headers

    def _print_title(self, title: str) -> None:
        console.print()
        console.print(
            Panel.fit(
                f"[bold magenta]{title}[/bold magenta]",
                border_style="magenta",
            )
        )

    def _print_status(self, status: int, suffix: str = "") -> None:
        style = "bold green" if 200 <= status < 300 else "bold red"
        text = f"HTTP {status}"
        if suffix:
            text += f" {suffix}"
        console.print(text, style=style)

    def _print_json_body(self, data: Any, label: str = "Body") -> None:
        console.print(f"[cyan]{label}:[/cyan]")
        # rprint já formata dict bonitinho e colorido
        rprint(data)

    # -------------------------------------------------------------------------
    # Workflows
    # -------------------------------------------------------------------------

    def initialize(self) -> None:
        self._print_title("1) initialize")
        msg_id = self._new_id()
        payload = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {
                    "roots": {"listChanged": True},
                    "sampling": {},
                    "elicitation": {},
                },
                "clientInfo": {
                    "name": "ExampleClient",
                    "version": "1.0.0",
                },
            },
        }

        response = self.client.post(
            self.base_url,
            headers=self._headers(),
            json=payload,
        )

        self._print_status(response.status_code)
        self.session_id = response.headers.get("Mcp-Session-Id")
        console.print(f"[cyan]Mcp-Session-Id:[/] {self.session_id}")
        self._print_json_body(response.json())

    def send_initialized_notification(self) -> None:
        self._print_title("2) notifications/initialized")
        payload = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }
        response = self.client.post(
            self.base_url,
            headers=self._headers(),
            json=payload,
        )

        self._print_status(response.status_code, "(esperado 202)")

    def list_tools(self) -> None:
        self._print_title("3) tools/list")
        msg_id = self._new_id()
        payload = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": "tools/list",
            "params": {
                "cursor": None,
            },
        }
        response = self.client.post(
            self.base_url,
            headers=self._headers(),
            json=payload,
        )
        self._print_status(response.status_code)
        self._print_json_body(response.json())

    def call_get_weather_simple(self) -> None:
        self._print_title("4) tools/call get_weather (resposta simples)")
        msg_id = self._new_id()
        payload = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": "tools/call",
            "params": {
                "name": "get_weather",
                "arguments": {
                    "location": "São Paulo",
                },
            },
        }
        response = self.client.post(
            self.base_url,
            headers=self._headers(),
            json=payload,
        )
        self._print_status(response.status_code)
        self._print_json_body(response.json())

    # -------------------------------------------------------------------------
    # SSE helpers
    # -------------------------------------------------------------------------

    def _consume_sse_stream(self, response: httpx.Response) -> None:
        """
        Consome um stream SSE onde cada evento vem em uma linha "data: {...}".
        Imprime cada mensagem JSON-RPC recebida.
        """
        for raw_line in response.iter_lines():
            if not raw_line:
                continue

            # httpx.iter_lines() geralmente retorna str, mas pode retornar bytes.
            if isinstance(raw_line, (bytes, bytearray)):
                line = raw_line.decode("utf-8")
            else:
                line = raw_line

            if not line.startswith("data: "):
                continue

            data_str = line[len("data: ") :]

            try:
                payload = json.loads(data_str)
            except json.JSONDecodeError:
                console.print(f"[yellow][SSE] linha inválida:[/] {line!r}")
                continue

            console.print(
                Panel.fit(
                    "[blue][SSE] mensagem recebida[/blue]",
                    border_style="blue",
                )
            )
            rprint(payload)

    # -------------------------------------------------------------------------
    # Streaming get_weather
    # -------------------------------------------------------------------------

    def call_get_weather_streaming(self) -> None:
        self._print_title("5) tools/call get_weather (streaming SSE)")
        msg_id = self._new_id()
        payload = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": "tools/call",
            "params": {
                "name": "get_weather",
                "arguments": {
                    "location": "São Paulo",
                    "forecastDays": 5,
                },
            },
        }

        with self.client.stream(
            "POST",
            self.base_url,
            headers=self._headers(),
            json=payload,
        ) as response:
            self._print_status(response.status_code)
            if response.headers.get("Content-Type", "").startswith("text/event-stream"):
                self._consume_sse_stream(response)
            else:
                console.print("[yellow]Resposta não é SSE, corpo:[/yellow]")
                self._print_json_body(response.json())

    # -------------------------------------------------------------------------
    # Resources
    # -------------------------------------------------------------------------

    def list_resources(self) -> None:
        self._print_title("6) resources/list")
        msg_id = self._new_id()
        payload = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": "resources/list",
            "params": {
                "cursor": None,
            },
        }
        response = self.client.post(
            self.base_url,
            headers=self._headers(),
            json=payload,
        )
        self._print_status(response.status_code)
        self._print_json_body(response.json())

    def read_terms_resource(self) -> None:
        self._print_title("7) resources/read resource://docs/terms")
        msg_id = self._new_id()
        payload = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": "resources/read",
            "params": {
                "uri": "resource://docs/terms",
            },
        }
        response = self.client.post(
            self.base_url,
            headers=self._headers(),
            json=payload,
        )
        self._print_status(response.status_code)
        self._print_json_body(response.json())

    # -------------------------------------------------------------------------
    # Notificações assíncronas via GET /mcp (SSE)
    # -------------------------------------------------------------------------

    def listen_notifications_via_get(self) -> None:
        self._print_title("8) GET /mcp para notificações assíncronas (SSE)")

        with self.client.stream(
            "GET",
            self.base_url,
            headers={
                "Accept": "text/event-stream",
                **({"Mcp-Session-Id": self.session_id} if self.session_id else {}),
            },
        ) as response:
            self._print_status(response.status_code)
            if response.headers.get("Content-Type", "").startswith("text/event-stream"):
                self._consume_sse_stream(response)
            else:
                console.print("[yellow]Resposta não é SSE.[/yellow]")

    # -------------------------------------------------------------------------
    # register_user + elicitation
    # -------------------------------------------------------------------------

    def call_register_user_with_elicitation(self) -> None:
        self._print_title("9) tools/call register_user com elicitation")
        call_id = self._new_id()
        payload = {
            "jsonrpc": "2.0",
            "id": call_id,
            "method": "tools/call",
            "params": {
                "name": "register_user",
                "arguments": {
                    "useElicitation": True,
                },
            },
        }

        with self.client.stream(
            "POST",
            self.base_url,
            headers=self._headers(),
            json=payload,
        ) as response:
            self._print_status(response.status_code)
            if not response.headers.get("Content-Type", "").startswith(
                "text/event-stream"
            ):
                console.print(
                    "[red]Resposta não é SSE, algo está incoerente com o demo.[/red]"
                )
                self._print_json_body(response.json())
                return

            # Loop lendo eventos SSE até receber o resultado final da tool
            for raw_line in response.iter_lines():
                if not raw_line:
                    continue

                if isinstance(raw_line, (bytes, bytearray)):
                    line = raw_line.decode("utf-8")
                else:
                    line = raw_line

                if not line.startswith("data: "):
                    continue

                data_str = line[len("data: ") :]
                payload = json.loads(data_str)

                console.print(
                    Panel.fit(
                        "[blue][SSE] mensagem recebida[/blue]",
                        border_style="blue",
                    )
                )
                rprint(payload)

                method = payload.get("method")
                msg_id = payload.get("id")

                # Se for uma elicitation/create, respondemos com dados fictícios
                if method == "elicitation/create" and msg_id is not None:
                    self._respond_to_elicitation(msg_id)

                # Se for o resultado final da tool register_user, saímos do loop
                if msg_id == call_id and "result" in payload:
                    console.print(
                        "[bold green]Recebido resultado final da tool register_user.[/bold green]"
                    )
                    break

    def _respond_to_elicitation(self, elic_id: int) -> None:
        """
        Simula a interação do usuário respondendo à elicitation.

        Em vez de pedir input no terminal, usamos valores de exemplo.
        """
        console.print(
            f"[cyan]Respondendo elicitation {elic_id} com dados de exemplo.[/cyan]"
        )
        response_payload: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": elic_id,
            "result": {
                "action": "accept",
                "content": {
                    "fullName": "Willams Sousa",
                    "email": "willams@example.com",
                    "acceptTerms": True,
                },
            },
        }
        response = self.client.post(
            self.base_url,
            headers=self._headers(),
            json=response_payload,
        )
        self._print_status(
            response.status_code,
            "(envio da resposta de elicitation)",
        )


def main() -> None:
    client = MCPClient()

    client.initialize()
    client.send_initialized_notification()
    client.list_tools()
    client.call_get_weather_simple()
    client.call_get_weather_streaming()
    client.list_resources()
    client.read_terms_resource()
    client.listen_notifications_via_get()
    client.call_register_user_with_elicitation()


if __name__ == "__main__":
    main()
