import pytest


@pytest.fixture
def october_data(client, auth_headers, category_ids, add_expense):
    food, transport = category_ids["Food"], category_ids["Transport"]
    client.patch(f"/categories/{food}", json={"monthly_budget": "400"}, headers=auth_headers)
    client.patch(f"/categories/{transport}", json={"monthly_budget": "1000"}, headers=auth_headers)

    add_expense(amount="300", spent_on="2026-10-05", category_id=food)
    add_expense(amount="200", spent_on="2026-10-18", category_id=food)
    add_expense(amount="150", spent_on="2026-10-07", category_id=transport)
    add_expense(amount="50", spent_on="2026-10-31")                       # uncategorised
    add_expense(amount="999", spent_on="2026-09-30", category_id=food)    # September: excluded


def test_monthly_report(client, auth_headers, october_data):
    response = client.get("/reports/monthly", params={"year": 2026, "month": 10}, headers=auth_headers)
    assert response.status_code == 200
    report = response.json()

    assert report["total"] == "700.00"
    assert report["count"] == 4

    rows = report["by_category"]
    assert [r["category_name"] for r in rows] == ["Food", "Transport", "Uncategorised"]   # biggest first

    food, transport, uncategorised = rows
    assert food["total"] == "500.00"
    assert food["remaining"] == "-100.00"
    assert food["over_budget"] is True
    assert transport["remaining"] == "850.00"
    assert transport["over_budget"] is False
    assert uncategorised["monthly_budget"] is None
    assert uncategorised["remaining"] is None


def test_monthly_report_empty_month(client, auth_headers):
    report = client.get("/reports/monthly", params={"year": 2026, "month": 1}, headers=auth_headers).json()
    assert report["total"] == "0.00"
    assert report["by_category"] == []


def test_yearly_report(client, auth_headers, october_data):
    report = client.get("/reports/yearly", params={"year": 2026}, headers=auth_headers).json()
    assert report["total"] == "1699.00"
    assert len(report["months"]) == 12
    assert report["months"][9] == {"month": 10, "total": "700.00", "count": 4}
    assert report["months"][8] == {"month": 9, "total": "999.00", "count": 1}
    assert report["months"][0] == {"month": 1, "total": "0.00", "count": 0}


def test_reports_only_include_my_expenses(client, other_headers, october_data):
    report = client.get("/reports/yearly", params={"year": 2026}, headers=other_headers).json()
    assert report["total"] == "0.00"


def test_invalid_month_is_422(client, auth_headers):
    assert client.get("/reports/monthly", params={"month": 13}, headers=auth_headers).status_code == 422
