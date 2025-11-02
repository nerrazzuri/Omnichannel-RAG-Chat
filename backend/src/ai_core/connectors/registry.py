from __future__ import annotations

from typing import Dict, Type

from .base import BaseConnector


class ConnectorRegistry:
    def __init__(self) -> None:
        self._reg: Dict[str, Type[BaseConnector]] = {}

    def register(self, name: str, cls: Type[BaseConnector]) -> None:
        self._reg[name.strip().lower()] = cls

    def get(self, name: str) -> Type[BaseConnector] | None:
        return self._reg.get(name.strip().lower())

    def names(self):
        return list(self._reg.keys())


registry = ConnectorRegistry()
