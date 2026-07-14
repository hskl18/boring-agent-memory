"""Boring Agent Memory."""

from importlib.metadata import PackageNotFoundError, version

from .api import memory_query

try:
    __version__ = version("boring-agent-memory")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = ["__version__", "memory_query"]
