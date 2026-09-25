import pytest

from brief import insider_summary
from data.insiders import parse_form4

FORM4 = """<?xml version="1.0"?>
<ownershipDocument>
  <documentType>4</documentType>
  <reportingOwner>
    <reportingOwnerId><rptOwnerName>Hill Elliott</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship>
      <isDirector>1</isDirector><isOfficer>1</isOfficer><officerTitle>PRESIDENT &amp; CEO</officerTitle>
    </reportingOwnerRelationship>
  </reportingOwner>
  <aff10b5One>0</aff10b5One>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionDate><value>2026-04-13</value></transactionDate>
      <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>23660</value></transactionShares>
        <transactionPricePerShare><value>42.27</value></transactionPricePerShare>
      </transactionAmounts>
      <postTransactionAmounts><sharesOwnedFollowingTransaction><value>150000</value></sharesOwnedFollowingTransaction></postTransactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <transactionDate><value>2026-04-13</value></transactionDate>
      <transactionCoding><transactionCode>F</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>500</value></transactionShares>
        <transactionPricePerShare><value></value></transactionPricePerShare>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>"""


def test_parse_form4_reads_trades_role_and_plan_flag():
    buy, withheld = parse_form4(FORM4)
    assert (buy["insider"], buy["role"], buy["code"]) == ("Hill Elliott", "PRESIDENT & CEO, Director", "P")
    assert buy["value"] == pytest.approx(23660 * 42.27)
    assert buy["owned_after"] == 150000 and not buy["planned"]
    assert withheld["code"] == "F" and withheld["price"] == 0.0  # blank price doesn't crash


def test_summary_separates_purchases_planned_sales_and_routine():
    trades = [
        {"code": "P", "insider": "CEO", "value": 1_000_000, "planned": False, "date": "2026-04-13"},
        {"code": "S", "insider": "CFO", "value": 200_000, "planned": True, "date": "2026-05-01"},
        {"code": "S", "insider": "Director", "value": 50_000, "planned": False, "date": "2026-06-01"},
        {"code": "A", "insider": "Director", "value": 0, "planned": False, "date": "2026-06-02"},
    ]
    g = insider_summary(trades)
    assert (g["buy_count"], g["buy_value"], g["buyers"]) == (1, 1_000_000, ["CEO"])
    assert (g["sell_count"], g["planned_sell_count"], g["discretionary_sell_value"]) == (2, 1, 50_000)
    assert g["routine_count"] == 1
    assert [t["date"] for t in g["open_market"]] == ["2026-06-01", "2026-05-01", "2026-04-13"]
