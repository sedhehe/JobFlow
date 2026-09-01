import importlib
import pkgutil
from typing import Type, Any

handlers: dict[str, Any] = {}


def register_handler(job_type: str, priority: str = "default"):
    """Decorator to auto-register handler classes by job type."""
    def decorator(cls: Type[Any]):
        instance = cls()
        instance.priority = priority
        handlers[job_type] = instance
        return cls
    return decorator


def discover_handlers():
    """Dynamically imports all handler modules in the handlers/ directory."""
    import handlers as handlers_pkg # /handlers folder
    for _, module_name, _ in pkgutil.iter_modules(handlers_pkg.__path__): # iterating through the folder
        if module_name != "registry": # skipping the registry file
            importlib.import_module(f"handlers.{module_name}") # importing the handler module


# Automatically discover and register all handlers on import
discover_handlers()