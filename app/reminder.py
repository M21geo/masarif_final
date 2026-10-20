"""Daily reminder content. Pure logic; the UI decides how to show it (in-app dialog)."""
import random
from datetime import datetime, timedelta
from typing import Optional

from . import money
from .debts import Debts
from .recurring import Recurring
from .repo import Repo


def settings(repo: Repo) -> dict:
    return {"enabled": repo.get_setting("reminder_enabled", "0") == "1",
            "time": repo.get_setting("reminder_time", "21:00") or "21:00"}


# Funny, lively messages: a different one each time (never the same twice in a row).
POOL = {
    "ar": {
        "no_tx": [
            "المحفظة تسأل عنك: وين رحت؟ ما سجلت شي اليوم 😅",
            "اليوم صرفت وما سجلت؟ الفلوس تنتظر تحقيق عاجل 🕵️",
            "فلوسك مثل الغنم، إذا ما عددتها تضيع! سجّل مصاريفك 🐑",
            "أبو الميزانية يسلّم عليك ويكلك: ولا معاملة اليوم؟! 🧐",
            "سجّل قبل لا تنسى.. ذاكرتنا مثل السمكة لو تدري 🐟",
            "دقيقة وحدة تسجل بيها، وسنة كاملة تفتخر بنفسك 💪",
            "حتى الشاي بالاستكان مصروف، سجّله! ☕",
            "التطبيق يشتاق لك.. اضغط + وسوّي له خاطر 🥺",
            "اليوم ما صار شي؟ أو ناسي تسجّل؟ 🤔",
            "الدينار يقول: دوّنوني قبل لا أهرب! 🏃",
            "نهارك سعيد! لا تخلّي مصاريف اليوم تمر بدون توثيق 📝",
            "مصروف بدون تسجيل مثل زواج بدون عرس: محد يدري بيه 🎉",
        ],
        "debt": [
            "{who} {name} ({amt}) {when} ⏰",
            "تذكير ودّي: دين {who} {name} بمبلغ {amt} {when} 🤝",
            "لا تنسى! {who} {name}: {amt} {when} 💸",
        ],
        "recurring": [
            "عندك {n} معاملة تكرارية مستحقة تنتظر تضغط «تنفيذ المستحق» 🔁",
            "معاملات تكرارية واقفة بالطابور ({n}).. نفّذها من الرئيسية 🚦",
        ],
        "titles": ["🔔 تذكير اليوم", "💸 يا صاحب الميزانية!", "📒 دفتر المصاريف يناديك", "🌞 وقت الحساب", "🧾 لحظة من وقتك"],
        "who_on": "عليك لـ", "who_for": "لك عند", "late": "متأخر", "today": "يستحق اليوم", "tomorrow": "يستحق غداً",
    },
    "en": {
        "no_tx": [
            "Your wallet is asking where you went. Nothing logged today 😅",
            "Spent something and didn't log it? Your money demands an investigation 🕵️",
            "Money is like sheep: if you don't count it, it wanders off 🐑",
            "Zero transactions today? Your budget is raising an eyebrow 🧐",
            "Log it before you forget. We have goldfish memory 🐟",
            "One minute of logging, a whole year of feeling smug 💪",
            "Even tea counts as spending. Log it! ☕",
            "The app misses you. Tap + and make it feel loved 🥺",
            "Nothing happened today, or did you forget to log? 🤔",
            "Your coins say: write me down before I run away! 🏃",
            "An unlogged expense is like a secret wedding: nobody knows 🎉",
            "Future you will thank present you for logging today 📝",
        ],
        "debt": [
            "{who} {name} ({amt}) {when} ⏰",
            "Friendly reminder: {who} {name}, {amt} {when} 🤝",
            "Don't forget! {who} {name}: {amt} {when} 💸",
        ],
        "recurring": [
            "{n} recurring transaction(s) are due. Tap “Run due” on Home 🔁",
            "{n} recurring item(s) waiting in line. Run them from Home 🚦",
        ],
        "titles": ["🔔 Today's reminder", "💸 Hey budget keeper!", "📒 Your ledger is calling", "🌞 Time to settle up", "🧾 A moment of your time"],
        "who_on": "You owe", "who_for": "Owed to you by", "late": "overdue", "today": "due today", "tomorrow": "due tomorrow",
    },
}


def _pick(repo: Repo, key: str, options: list, rng) -> str:
    """Random choice that avoids repeating the previous one for this key."""
    last = repo.get_setting("reminder_last_" + key, "")
    pool = [i for i in range(len(options)) if str(i) != last] or list(range(len(options)))
    i = rng.choice(pool)
    repo.set_setting("reminder_last_" + key, str(i))
    return options[i]


def lines(repo: Repo, today: str, rng=None) -> list:
    """What is worth reminding about right now (empty = nothing). Wording changes every time."""
    rng = rng or random.Random()
    P = POOL.get(repo.get_setting("lang", "ar") or "ar", POOL["ar"])
    out = []
    if not repo.conn.execute("SELECT 1 FROM transactions WHERE date=? LIMIT 1", (today,)).fetchone():
        out.append(_pick(repo, "no_tx", P["no_tx"], rng))
    tomorrow = (datetime.fromisoformat(today) + timedelta(days=1)).date().isoformat()
    for d in Debts(repo).list_debts(include_settled=False, today=today):
        if d["due_date"] and d["due_date"] <= tomorrow:
            amt = money.fmt(d["next_amount"] or d["remaining"], d["currency"])
            when = P["late"] if d["due_date"] < today else (P["today"] if d["due_date"] == today else P["tomorrow"])
            who = P["who_on"] if d["direction"] == "on" else P["who_for"]
            out.append(_pick(repo, "debt", P["debt"], rng).format(who=who, name=d["person_name"], amt=amt, when=when))
    pending = Recurring(repo).pending(today)
    if pending["count"]:
        out.append(_pick(repo, "recurring", P["recurring"], rng).format(n=pending["count"]))
    return out


def title(repo: Repo, rng=None) -> str:
    P = POOL.get(repo.get_setting("lang", "ar") or "ar", POOL["ar"])
    return _pick(repo, "title", P["titles"], rng or random.Random())


def due(repo: Repo, now: Optional[datetime] = None) -> list:
    """Reminder lines to show now, or [] (disabled, too early, already shown today, or nothing to say).
    Does NOT mark as shown - call mark_shown() when the user actually saw it."""
    now = now or datetime.now()
    cfg = settings(repo)
    if not cfg["enabled"] or now.strftime("%H:%M") < cfg["time"]:
        return []
    today = now.date().isoformat()
    if repo.get_setting("reminder_last") == today:
        return []
    return lines(repo, today)


def mark_shown(repo: Repo, now: Optional[datetime] = None) -> None:
    repo.set_setting("reminder_last", (now or datetime.now()).date().isoformat())
