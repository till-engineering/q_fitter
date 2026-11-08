"""Methods: base class, @register and automatic discovery.

Every file in q_fitter/pore_models, q_fitter/stress_models and q_fitter/fits is imported once at
start (files starting with "_" are skipped, e.g. _template.py). @register("name") files a class
under its kind; config.yaml selects it by that name, all other keys of the entry are its parameters.
"""

import importlib
import pkgutil

_methods: dict[str, dict[str, type]] = {}
_discovered = False
PACKAGES = ("pore_models", "stress_models", "fits")


class Method:
    """Base of all methods. `params` documents the parameters (name -> description); each one
    must be given in config.yaml and is available as an attribute (self.<name>)."""

    kind = ""                   # set by the base classes: "pore_model" | "stress_model" | "fit"
    name = ""                   # set by @register
    params: dict[str, str] = {}

    def __init__(self, **values):
        missing = set(self.params) - set(values)
        unknown = set(values) - set(self.params)
        if missing or unknown:
            raise ValueError(f"{self.kind} '{self.name}': missing parameters {sorted(missing) or '-'}, "
                             f"unknown parameters {sorted(unknown) or '-'} (expected: {sorted(self.params) or 'none'})")
        for key, value in values.items():
            setattr(self, key, value)

    def describe(self) -> str:
        values = ", ".join(f"{key}={getattr(self, key)!r}" for key in self.params)
        return f"{self.name}({values})"


def register(name: str):
    """Class decorator: make a method selectable in config.yaml under `name`."""

    def decorator(cls):
        methods = _methods.setdefault(cls.kind, {})
        if name in methods:
            raise ValueError(f"{cls.kind} '{name}' registered twice: {methods[name].__module__} and {cls.__module__}")
        cls.name = name
        methods[name] = cls
        return cls

    return decorator


def discover() -> None:
    global _discovered
    if _discovered:
        return
    for package_name in PACKAGES:
        package = importlib.import_module(f"q_fitter.{package_name}")
        for module in pkgutil.iter_modules(package.__path__):
            if not module.name.startswith("_"):
                importlib.import_module(f"{package.__name__}.{module.name}")
    _discovered = True


def create(kind: str, entry: dict) -> Method:
    """Instantiate the method of a config entry {name: ..., <parameters>}."""
    discover()
    values = dict(entry)
    name = values.pop("name")
    methods = _methods.get(kind, {})
    if name not in methods:
        raise ValueError(f"unknown {kind} '{name}' (available: {', '.join(sorted(methods)) or 'none'})")
    return methods[name](**values)


def available() -> dict[str, list[tuple[str, str]]]:
    """All registered methods per kind: (name, first line of the docstring)."""
    discover()
    return {kind: [(name, (cls.__doc__ or "").strip().split("\n")[0]) for name, cls in sorted(methods.items())]
            for kind, methods in _methods.items()}
