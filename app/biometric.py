"""Fingerprint / face unlock.

Flet 0.28 has no biometric service. Newer Flet releases ship the `flet-local-auth` package (Flutter local_auth).
This adapter uses it when it is installed and otherwise reports "not available", so the password lock keeps
working everywhere and the fingerprint switch just stays off. Nothing here can break the app: every call is guarded.
"""
import inspect

_service = {"obj": None, "tried": False}


def _load(page):
    if _service["tried"]:
        return _service["obj"]
    _service["tried"] = True
    try:
        import flet_local_auth as fla  # type: ignore
        cls = getattr(fla, "LocalAuthentication", None) or getattr(fla, "LocalAuth", None)
        obj = cls()
        try:
            page.services.append(obj)       # newer Flet: services are registered on the page
        except Exception:
            try:
                page.overlay.append(obj)
            except Exception:
                pass
        _service["obj"] = obj
    except Exception:
        _service["obj"] = None
    return _service["obj"]


async def _maybe_await(v):
    return await v if inspect.isawaitable(v) else v


async def available(page) -> bool:
    obj = _load(page)
    if obj is None:
        return False
    try:
        for name in ("is_device_supported", "can_check_biometrics"):
            fn = getattr(obj, name, None)
            if fn:
                return bool(await _maybe_await(fn()))
    except Exception:
        pass
    return False


async def authenticate(page, reason: str) -> bool:
    obj = _load(page)
    if obj is None:
        return False
    try:
        return bool(await _maybe_await(obj.authenticate(reason)))
    except Exception:
        return False
