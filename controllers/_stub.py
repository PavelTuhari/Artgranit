from __future__ import annotations


class _StubMeta(type):
    def __getattr__(cls, name):
        def _fn(*args, **kwargs):
            return {"success": False, "error": f"{cls.__name__}.{name} is not available in local fallback controllers"}
        return _fn


class StubController(metaclass=_StubMeta):
    pass
