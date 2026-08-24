from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import _billing_tariff_summary_lines


mixed = _billing_tariff_summary_lines(
    [
        {"payment_amount": 20},
        {"payment_amount": "20.00"},
        {"payment_amount": 10},
    ]
)
assert mixed == [
    "- тариф 20 €: 2 оплат; сумма: 40.00 €",
    "- тариф 10 €: 1 оплат; сумма: 10.00 €",
    "- всего: 3 оплат; сумма: 50.00 €",
]

single = _billing_tariff_summary_lines(
    [{"payment_amount": 10}, {"payment_amount": 10.0}]
)
assert single == ["- тариф 10 €: 2 оплат; сумма: 20.00 €"]

assert _billing_tariff_summary_lines([]) == [
    "- оплаченные: 0",
    "- сумма: 0.00 €",
]

print("billing_tariff_summary_smoke OK")
