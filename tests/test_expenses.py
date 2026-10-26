def test_create_expense(client, auth_headers, category_ids):
    response = client.post("/expenses", json={
        "amount": "249.50",
        "description": "Lunch with team",
        "spent_on": "2026-10-20",
        "payment_method": "upi",
        "category_id": category_ids["Food"],
    }, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["amount"] == "249.50"
    assert data["payment_method"] == "upi"
    assert data["category"] == {"id": category_ids["Food"], "name": "Food"}


def test_expense_requires_login(client):
    assert client.get("/expenses").status_code == 401


def test_invalid_amounts_are_422(client, auth_headers):
    for amount in ["0", "-5", "10.999", "abc"]:
        response = client.post("/expenses", json={"amount": amount, "description": "x"}, headers=auth_headers)
        assert response.status_code == 422, amount


def test_invalid_payment_method_is_422(client, auth_headers):
    response = client.post("/expenses", json={"amount": "10", "description": "x", "payment_method": "bitcoin"},
                           headers=auth_headers)
    assert response.status_code == 422


def test_cannot_use_another_users_category(client, auth_headers, other_headers, category_ids):
    response = client.post("/expenses", json={
        "amount": "10", "description": "sneaky", "category_id": category_ids["Food"],
    }, headers=other_headers)
    assert response.status_code == 400


def test_other_user_cannot_see_my_expense(client, other_headers, add_expense):
    expense = add_expense()
    assert client.get(f"/expenses/{expense['id']}", headers=other_headers).status_code == 404
    assert client.get("/expenses", headers=other_headers).json()["total"] == 0


def test_filters(client, auth_headers, category_ids, add_expense):
    add_expense(amount="50", description="Bus ticket", spent_on="2026-10-01", category_id=category_ids["Transport"])
    add_expense(amount="500", description="Dinner", spent_on="2026-10-15", category_id=category_ids["Food"])
    add_expense(amount="1200", description="Electricity bill", spent_on="2026-11-02",
                category_id=category_ids["Bills"], payment_method="netbanking")
    add_expense(amount="80", description="Snacks", spent_on="2026-10-20")   # uncategorised

    def total(**params):
        response = client.get("/expenses", params=params, headers=auth_headers)
        assert response.status_code == 200, response.text
        return response.json()["total"]

    assert total() == 4
    assert total(start_date="2026-10-01", end_date="2026-10-31") == 3
    assert total(category_id=category_ids["Food"]) == 1
    assert total(uncategorised="true") == 1
    assert total(min_amount="100") == 2
    assert total(payment_method="netbanking") == 1
    assert total(search="BILL") == 1                  # case-insensitive


def test_bad_date_range_is_400(client, auth_headers):
    response = client.get("/expenses", params={"start_date": "2026-10-31", "end_date": "2026-10-01"},
                          headers=auth_headers)
    assert response.status_code == 400


def test_sorting_and_pagination(client, auth_headers, add_expense):
    for amount in ["30", "10", "20"]:
        add_expense(amount=amount)

    page = client.get("/expenses", params={"sort": "highest", "limit": 2}, headers=auth_headers).json()
    assert page["total"] == 3
    assert [e["amount"] for e in page["items"]] == ["30.00", "20.00"]

    page = client.get("/expenses", params={"sort": "highest", "limit": 2, "offset": 2}, headers=auth_headers).json()
    assert [e["amount"] for e in page["items"]] == ["10.00"]


def test_limit_is_capped(client, auth_headers):
    assert client.get("/expenses", params={"limit": 500}, headers=auth_headers).status_code == 422


def test_patch_changes_only_sent_fields(client, auth_headers, add_expense):
    expense = add_expense(amount="100", description="Groceries")
    response = client.patch(f"/expenses/{expense['id']}", json={"amount": "120.75"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["amount"] == "120.75"
    assert response.json()["description"] == "Groceries"


def test_patch_amount_null_is_422(client, auth_headers, add_expense):
    expense = add_expense()
    response = client.patch(f"/expenses/{expense['id']}", json={"amount": None}, headers=auth_headers)
    assert response.status_code == 422


def test_patch_category_null_uncategorises(client, auth_headers, category_ids, add_expense):
    expense = add_expense(category_id=category_ids["Food"])
    response = client.patch(f"/expenses/{expense['id']}", json={"category_id": None}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["category"] is None


def test_delete_expense(client, auth_headers, add_expense):
    expense = add_expense()
    assert client.delete(f"/expenses/{expense['id']}", headers=auth_headers).status_code == 204
    assert client.get(f"/expenses/{expense['id']}", headers=auth_headers).status_code == 404
    assert client.delete(f"/expenses/{expense['id']}", headers=auth_headers).status_code == 404
