"""Timeout-wrapped ProxyProvider — evita che backends lenti blocchino tools/list.

Il proxy ARIA carica fino a 19 backends MCP dal catalogo. Alcuni backends
(es. airbnb via npx, google_workspace con OAuth server) impiegano decine di
secondi per inizializzarsi. FastMCP ProxyProvider attende che TUTTI i backends
rispondano a list_tools prima di restituire il risultato, causando un hang
che supera il timeout di KiloCode.

Questa classe estende ProxyProvider con un timeout asincrono configurabile:
se un backend non risponde entro `list_timeout_s`, si procede con gli strumenti
già disponibili, loggando un warning. Gli strumenti mancanti potranno essere
scoperti in una successiva chiamata (la cache viene invalidata).

Rispetta:
- P2 (Upstream Invariance): non modifica FastMCP, lo estende via subclassing
- P8 (Tool Priority Ladder): mantiene l'architettura proxy esistente
- P10 (Self-Documenting Evolution): modifica circoscritta a build_proxy()
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from fastmcp.server.providers.proxy import ProxyProvider

from aria.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fastmcp.server.providers.proxy import ClientFactoryT
    from fastmcp.tools.base import Tool

logger = get_logger("aria.mcp.proxy.provider")

DEFAULT_LIST_TIMEOUT_S: float = 30.0


class TimeoutProxyProvider(ProxyProvider):
    """ProxyProvider with a timeout on list_tools.

    Se la raccolta degli strumenti dai backends richiede più di
    `list_timeout_s` secondi, restituisce una lista vuota e logga
    un warning. I backends lenti vengono riprovati alla prossima
    chiamata (invalidate cache).

    Args:
        client_factory: factory per creare client connessi ai backends
        cache_ttl: TTL della cache (default 300s)
        list_timeout_s: timeout massimo per list_tools (default 30s)
    """

    def __init__(
        self,
        client_factory: ClientFactoryT,
        *,
        cache_ttl: float | None = None,
        list_timeout_s: float = DEFAULT_LIST_TIMEOUT_S,
    ) -> None:
        super().__init__(client_factory, cache_ttl=cache_ttl)
        self._list_timeout_s = list_timeout_s

    async def _list_tools(self) -> Sequence[Tool]:
        """List tools with a timeout.

        Se il timeout scade, restituisce [] senza fare cache, così
        la prossima chiamata riprova da capo.
        """
        try:
            return await asyncio.wait_for(
                super()._list_tools(),
                timeout=self._list_timeout_s,
            )
        except TimeoutError:
            logger.warning(
                "proxy.list_tools_timeout",
                extra={"timeout_s": self._list_timeout_s},
            )
            # Non fare cache: la prossima chiamata riprova
            self._tools_cache = None
            return []
        except Exception:
            logger.exception("proxy.list_tools_error")
            self._tools_cache = None
            return []
