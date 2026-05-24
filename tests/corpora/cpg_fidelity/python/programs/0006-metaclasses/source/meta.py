"""Metaclass coverage: __init_subclass__ / metaclass-driven dispatch.

Construct under test: metaclass and `__init_subclass__` registration (DOC §4.3
`metaclasses`). The registry lookup call is `dynamic` (target chosen at runtime);
the direct `register` helper call is a static edge.
"""


class PluginMeta(type):
    registry = {}

    def __new__(mcs, name, bases, ns):
        cls = super().__new__(mcs, name, bases, ns)
        PluginMeta.registry[name] = cls
        return cls


class Base(metaclass=PluginMeta):
    def run(self):
        return 0


class Worker(Base):
    def run(self):
        return 1


def register(name, cls):
    PluginMeta.registry[name] = cls
    return name


def make(name):
    cls = PluginMeta.registry[name]
    return cls()
