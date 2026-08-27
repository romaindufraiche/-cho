"""Point-in-time Fundamental/Valuation inputs from SEC EDGAR XBRL company
facts, annual (10-K) only: each row is valid from its `filed` date (when the
number actually became public) until the next 10-K is filed, so joining on
`filed <= as_of_date` can never leak a number before the market could have
known it - the whole point of section 9's walk-forward requirement.

US filers only. SEC EDGAR has no coverage for foreign private issuers that
report under IFRS to their home regulator instead of filing 10-K/10-Q with
the SEC - which is every European name in this project's universe (Siemens,
LVMH, SAP, ASML, L'Oreal, ...). For those, `point_in_time_fundamentals`
returns an empty DataFrame; callers should fall back to the Technical/Risk-
only model rather than guessing.

XBRL tagging varies company to company and over time (e.g. many switched
from "Revenues" to "RevenueFromContractWithCustomerExcludingAssessedTax"
around the 2018 ASC 606 adoption), so each concept is resolved by merging
every known alias rather than trusting a single tag.
"""

from __future__ import annotations

import pandas as pd

from project_alpha.data.sources.sec_edgar import extract_concept, get_company_facts, lookup_cik

_REVENUE_TAGS = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"]
_COST_OF_REVENUE_TAGS = ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"]
_GROSS_PROFIT_TAGS = ["GrossProfit"]
_OPERATING_INCOME_TAGS = ["OperatingIncomeLoss"]
_OCF_TAGS = [
    "NetCashProvidedByUsedInOperatingActivities",
    "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
]
_CAPEX_TAGS = ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"]
_DA_TAGS = [
    "DepreciationDepletionAndAmortization",
    "DepreciationAmortizationAndAccretionNet",
    "DepreciationAndAmortization",
]
_LT_DEBT_TAGS = ["LongTermDebtNoncurrent", "LongTermDebt"]
_ST_DEBT_TAGS = ["LongTermDebtCurrent", "DebtCurrent", "ShortTermBorrowings"]
_CASH_TAGS = ["CashAndCashEquivalentsAtCarryingValue"]
_EPS_TAGS = ["EarningsPerShareDiluted"]


def _all_available(facts: dict, tags: list[str]) -> list[dict]:
    """Concatenates rows across every alias for a concept - companies
    switch XBRL tags over time (e.g. "Revenues" -> the ASC-606
    "RevenueFromContractWithCustomerExcludingAssessedTax" tag around 2018),
    so picking only the first alias with any data would silently drop every
    fiscal year reported under a tag it switched to later."""
    rows: list[dict] = []
    for tag in tags:
        rows.extend(extract_concept(facts, tag))
    return rows


def _annual_rows(rows: list[dict]) -> dict[int, dict]:
    """Keyed by fiscal year, restricted to 10-K rows covering a ~1-year
    duration (XBRL also reports quarterly/YTD slices of the same concept;
    mixing them in would silently corrupt the annual figures)."""
    by_fy: dict[int, dict] = {}
    for r in rows:
        if r.get("form") != "10-K":
            continue
        start, end, fy = r.get("start"), r.get("end"), r.get("fy")
        if fy is None:
            continue
        if start and end:
            days = (pd.Timestamp(end) - pd.Timestamp(start)).days
            if not (330 <= days <= 400):
                continue
        if fy not in by_fy or r["filed"] > by_fy[fy]["filed"]:
            by_fy[fy] = r
    return by_fy


def _instant_rows(rows: list[dict]) -> dict[str, dict]:
    """Balance-sheet (instant) concepts keyed by `end` date, keeping the
    latest-filed value seen for a given date (covers restatements)."""
    by_end: dict[str, dict] = {}
    for r in rows:
        end = r.get("end")
        if not end:
            continue
        if end not in by_end or r["filed"] > by_end[end]["filed"]:
            by_end[end] = r
    return by_end


def _nearest_instant_on_or_before(by_end: dict[str, dict], target_end: str) -> float | None:
    if not by_end:
        return None
    candidates = [e for e in by_end if e <= target_end]
    if not candidates:
        return None
    return by_end[max(candidates)]["val"]


def point_in_time_fundamentals(ticker: str) -> pd.DataFrame:
    """One row per 10-K filing, indexed by `filed` date. Empty if the
    ticker doesn't file 10-Ks with the SEC or has no usable XBRL history."""
    cik = lookup_cik(ticker)
    if cik is None:
        return pd.DataFrame()
    try:
        facts = get_company_facts(cik)
    except Exception:
        return pd.DataFrame()

    revenue = _annual_rows(_all_available(facts, _REVENUE_TAGS))
    if not revenue:
        return pd.DataFrame()
    gross_profit = _annual_rows(_all_available(facts, _GROSS_PROFIT_TAGS))
    cost_of_revenue = _annual_rows(_all_available(facts, _COST_OF_REVENUE_TAGS))
    operating_income = _annual_rows(_all_available(facts, _OPERATING_INCOME_TAGS))
    ocf = _annual_rows(_all_available(facts, _OCF_TAGS))
    capex = _annual_rows(_all_available(facts, _CAPEX_TAGS))
    da = _annual_rows(_all_available(facts, _DA_TAGS))
    eps = _annual_rows(_all_available(facts, _EPS_TAGS))
    lt_debt = _instant_rows(_all_available(facts, _LT_DEBT_TAGS))
    st_debt = _instant_rows(_all_available(facts, _ST_DEBT_TAGS))
    cash = _instant_rows(_all_available(facts, _CASH_TAGS))

    rows = []
    for fy in sorted(revenue.keys()):
        rev_row = revenue[fy]
        rev = rev_row["val"]
        prior = revenue.get(fy - 1)
        revenue_growth_yoy = (rev - prior["val"]) / abs(prior["val"]) if prior and prior["val"] else None

        gp_row = gross_profit.get(fy)
        cor_row = cost_of_revenue.get(fy)
        if gp_row and rev:
            gross_margin = gp_row["val"] / rev
        elif cor_row and rev:
            gross_margin = (rev - cor_row["val"]) / rev
        else:
            gross_margin = None

        op_row = operating_income.get(fy)
        operating_margin = (op_row["val"] / rev) if op_row and rev else None

        ocf_row, capex_row, da_row = ocf.get(fy), capex.get(fy), da.get(fy)
        free_cash_flow = (ocf_row["val"] - abs(capex_row["val"])) if ocf_row and capex_row else None
        free_cash_flow_margin = (free_cash_flow / rev) if free_cash_flow is not None and rev else None

        ebitda = (op_row["val"] + da_row["val"]) if op_row and da_row else None
        end_date = rev_row["end"]
        lt = _nearest_instant_on_or_before(lt_debt, end_date)
        st = _nearest_instant_on_or_before(st_debt, end_date)
        csh = _nearest_instant_on_or_before(cash, end_date)
        net_debt_to_ebitda = None
        if ebitda and (lt is not None or st is not None):
            net_debt_to_ebitda = ((lt or 0) + (st or 0) - (csh or 0)) / ebitda

        eps_row = eps.get(fy)

        rows.append(
            {
                "fy": fy,
                "filed": rev_row["filed"],
                "revenue_growth_yoy": revenue_growth_yoy,
                "gross_margin": gross_margin,
                "operating_margin": operating_margin,
                "free_cash_flow_margin": free_cash_flow_margin,
                "net_debt_to_ebitda": net_debt_to_ebitda,
                "eps_diluted": eps_row["val"] if eps_row else None,
            }
        )

    df = pd.DataFrame(rows)
    df["filed"] = pd.to_datetime(df["filed"])
    return df.sort_values("filed").set_index("filed")


def as_of(df: pd.DataFrame, as_of_date) -> dict | None:
    """Latest filing with `filed <= as_of_date` - i.e. what the market
    actually knew on that date. None if nothing had been filed yet."""
    if df.empty:
        return None
    eligible = df[df.index <= pd.Timestamp(as_of_date)]
    if eligible.empty:
        return None
    return eligible.iloc[-1].to_dict()
