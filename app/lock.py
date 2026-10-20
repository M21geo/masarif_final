"""App / More-tab lock: password (PBKDF2 hash, never stored in clear), recovery code, attempt throttling.

Settings keys: lock_hash, lock_salt, lock_recovery (hash of the recovery code), lock_app ("1"), lock_more ("1"),
lock_bio ("1"). The lock is a convenience barrier against someone casually opening the app on the phone;
the data file itself is not encrypted.
"""
import hashlib
import hmac
import secrets
import time
from typing import Optional

from .repo import AppError, Repo

ITERATIONS = 120_000
MIN_LENGTH = 4
MAX_FREE_ATTEMPTS = 5
COOLDOWN_SECONDS = 30
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # no look-alike characters

_attempts = {"n": 0, "until": 0.0}


def _hash(secret: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), bytes.fromhex(salt), ITERATIONS).hex()


def has_password(repo: Repo) -> bool:
    return bool(repo.get_setting("lock_hash", ""))


def set_password(repo: Repo, password: str, current: Optional[str] = None) -> str:
    """Set or change the password. Changing needs the current one. Returns a NEW recovery code (show it once)."""
    if has_password(repo) and not check_password(repo, current or "", count=False):
        raise AppError("كلمة السر الحالية غير صحيحة")
    password = password.strip()
    if len(password) < MIN_LENGTH:
        raise AppError(f"كلمة السر لازم تكون {MIN_LENGTH} خانات أو أكثر")
    salt = secrets.token_hex(16)
    code = "".join(secrets.choice(_ALPHABET) for _ in range(8))
    repo.set_setting("lock_salt", salt)
    repo.set_setting("lock_hash", _hash(password, salt))
    repo.set_setting("lock_recovery", _hash(code, salt))
    return code


def check_password(repo: Repo, password: str, count: bool = True) -> bool:
    """True if the password is right. After 5 wrong tries entering is blocked for 30 seconds."""
    if count and seconds_blocked() > 0:
        raise AppError(f"محاولات كثيرة. انتظر {seconds_blocked()} ثانية")
    stored, salt = repo.get_setting("lock_hash", ""), repo.get_setting("lock_salt", "")
    ok = bool(stored) and hmac.compare_digest(_hash((password or "").strip(), salt), stored)
    if count:
        if ok:
            _attempts.update(n=0, until=0.0)
        else:
            _attempts["n"] += 1
            if _attempts["n"] >= MAX_FREE_ATTEMPTS:
                _attempts.update(n=0, until=time.time() + COOLDOWN_SECONDS)
    return ok


def seconds_blocked() -> int:
    return max(0, int(round(_attempts["until"] - time.time())))


def recover(repo: Repo, code: str) -> bool:
    """Forgot the password: the recovery code removes the lock completely (then set a new password)."""
    salt, stored = repo.get_setting("lock_salt", ""), repo.get_setting("lock_recovery", "")
    if stored and hmac.compare_digest(_hash((code or "").strip().upper(), salt), stored):
        remove(repo)
        return True
    return False


def remove(repo: Repo) -> None:
    for k in ("lock_hash", "lock_salt", "lock_recovery"):
        repo.set_setting(k, "")
    for k in ("lock_app", "lock_more", "lock_bio"):
        repo.set_setting(k, "0")


def options(repo: Repo) -> dict:
    on = has_password(repo)
    return {"password": on,
            "app": on and repo.get_setting("lock_app", "0") == "1",
            "more": on and repo.get_setting("lock_more", "0") == "1",
            "bio": on and repo.get_setting("lock_bio", "0") == "1"}


def set_option(repo: Repo, name: str, value: bool) -> None:
    if name not in ("app", "more", "bio"):
        raise AppError("خيار غير معروف")
    if value and not has_password(repo):
        raise AppError("حدد كلمة سر أولاً")
    repo.set_setting("lock_" + name, "1" if value else "0")
