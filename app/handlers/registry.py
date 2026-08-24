import importlib
import pkgutil
from typing import Type, Any

handlers: dict[str, Any] = {}


def register_handler(job_type: str):
    """Decorator to auto-register handler classes by job type."""
    def decorator(cls: Type[Any]):
        handlers[job_type] = cls()
        return cls
    return decorator


def discover_handlers():
    """Dynamically imports all handler modules in the handlers/ directory."""
    import handlers as handlers_pkg
    for _, module_name, _ in pkgutil.iter_modules(handlers_pkg.__path__):
        if module_name != "registry":
            importlib.import_module(f"handlers.{module_name}")


# Automatically discover and register all handlers on import
discover_handlers()