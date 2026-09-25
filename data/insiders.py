"""Insider transactions from SEC Form 4 filings.

Insiders (directors, officers, 10%+ owners) must file a Form 4 within two
business days of trading, so this is close to live. The transaction code
separates open-market purchases (P) and sales (S), the informative trades, from
routine ones: awards (A), option exercises (M), shares withheld for tax (F),
gifts (G) and so on.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

CODE_LABELS = {
    "P": "Open-market purchase", "S": "Open-market sale", "A": "Award / grant",
    "M": "Option exercise", "F": "Tax withholding", "G": "Gift", "D": "Returned to company",
    "C": "Conversion", "X": "Option exercise", "J": "Other",
}


def _text(node, path: str) -> str:
    found = node.find(path) if node is not None else None
    return (found.text or "").strip() if found is not None and found.text else ""


def _num(node, path: str) -> float:
    try:
        return float(_text(node, path))
    except ValueError:
        return 0.0


def _flag(node, path: str) -> bool:
    return _text(node, path).lower() in ("1", "true")


def _role(rel) -> str:
    parts = []
    if _flag(rel, "isOfficer"):
        parts.append(_text(rel, "officerTitle") or "Officer")
    if _flag(rel, "isDirector"):
        parts.append("Director")
    if _flag(rel, "isTenPercentOwner"):
        parts.append("10% owner")
    return ", ".join(parts) or "Other"


def parse_form4(xml_text: str) -> list[dict]:
    """Non-derivative (common stock) transactions in one Form 4."""
    root = ET.fromstring(xml_text)
    owners = root.findall("reportingOwner")
    insider = " & ".join(_text(o, "reportingOwnerId/rptOwnerName") for o in owners) or "Unknown"
    role = _role(owners[0].find("reportingOwnerRelationship")) if owners else "Other"
    # Rule 10b5-1: a trading plan set up in advance, so the trade says little about today's view
    plan = _flag(root, "aff10b5One")
    trades = []
    for t in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        shares = _num(t, "transactionAmounts/transactionShares/value")
        price = _num(t, "transactionAmounts/transactionPricePerShare/value")
        trades.append({
            "date": _text(t, "transactionDate/value"),
            "insider": insider,
            "role": role,
            "code": _text(t, "transactionCoding/transactionCode"),
            "shares": shares,
            "price": price,
            "value": shares * price,
            "owned_after": _num(t, "postTransactionAmounts/sharesOwnedFollowingTransaction/value"),
            "planned": plan,
        })
    return trades
