import pandas as pd

from project_alpha.data.sources.sec_edgar_fundamentals import (
    _all_available,
    _annual_rows,
    _instant_rows,
    _nearest_instant_on_or_before,
    as_of,
)


def test_all_available_merges_tag_aliases():
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {"units": {"USD": [{"end": "2017-09-30", "val": 100, "fy": 2017, "form": "10-K", "filed": "2017-11-01", "start": "2016-10-01"}]}},
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {"USD": [{"end": "2018-09-30", "val": 120, "fy": 2018, "form": "10-K", "filed": "2018-11-01", "start": "2017-10-01"}]}
                },
            }
        }
    }
    rows = _all_available(facts, ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"])
    assert {r["fy"] for r in rows} == {2017, 2018}


def test_annual_rows_excludes_quarterly_durations():
    rows = [
        {"form": "10-K", "start": "2019-10-01", "end": "2020-09-30", "fy": 2020, "filed": "2020-11-01", "val": 100},
        {"form": "10-Q", "start": "2020-07-01", "end": "2020-09-30", "fy": 2020, "filed": "2020-08-01", "val": 25},
    ]
    by_fy = _annual_rows(rows)
    assert set(by_fy) == {2020}
    assert by_fy[2020]["val"] == 100


def test_annual_rows_keeps_latest_filed_restatement():
    rows = [
        {"form": "10-K", "start": "2019-01-01", "end": "2019-12-31", "fy": 2019, "filed": "2020-02-01", "val": 100},
        {"form": "10-K", "start": "2019-01-01", "end": "2019-12-31", "fy": 2019, "filed": "2021-02-01", "val": 105},
    ]
    by_fy = _annual_rows(rows)
    assert by_fy[2019]["val"] == 105


def test_instant_rows_and_nearest_lookup():
    rows = [
        {"end": "2019-12-31", "val": 10, "filed": "2020-02-01"},
        {"end": "2020-12-31", "val": 20, "filed": "2021-02-01"},
    ]
    by_end = _instant_rows(rows)
    assert _nearest_instant_on_or_before(by_end, "2020-12-31") == 20
    assert _nearest_instant_on_or_before(by_end, "2020-06-30") == 10
    assert _nearest_instant_on_or_before(by_end, "2019-01-01") is None


def test_as_of_never_leaks_future_filing():
    df = pd.DataFrame(
        {"revenue_growth_yoy": [0.1, 0.2]},
        index=pd.to_datetime(["2020-11-05", "2021-11-05"]),
    )
    assert as_of(df, "2021-01-01")["revenue_growth_yoy"] == 0.1
    assert as_of(df, "2021-11-05")["revenue_growth_yoy"] == 0.2
    assert as_of(df, "2020-01-01") is None


def test_as_of_empty_dataframe_returns_none():
    assert as_of(pd.DataFrame(), "2021-01-01") is None
