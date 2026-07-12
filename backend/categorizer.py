"""Learned merchant→category rules.

User-taught rules (CategoryRule rows) always win over the static keyword
guessers: after any parser has done its keyword guess, run the transactions
through apply_rules(). Longest pattern wins so a specific merchant rule beats
a broad one.
"""
from sqlalchemy.orm import Session
from models import CategoryRule


def load_rules(db: Session):
    rules = db.query(CategoryRule).all()
    return sorted(
        ((r.pattern.lower(), r.category) for r in rules if r.pattern),
        key=lambda x: -len(x[0]),
    )


def apply_rules(description: str, fallback: str, rules) -> str:
    d = (description or "").lower()
    for pattern, category in rules:
        if pattern in d:
            return category
    return fallback


def uncategorized_descriptions(txns, limit: int = 15):
    """Distinct descriptions that stayed 'Other' — offered to the user to teach."""
    seen, out = set(), []
    for t in txns:
        if t.get("category") != "Other":
            continue
        desc = (t.get("description") or "").strip()
        key = desc.lower()
        if desc and key not in seen:
            seen.add(key)
            out.append(desc)
            if len(out) >= limit:
                break
    return out
