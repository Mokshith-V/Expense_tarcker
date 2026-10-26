def test_create_category(client, auth_headers):
    response = client.post("/categories", json={"name": "  Rent ", "monthly_budget": "15000"},
                           headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Rent"                  # whitespace stripped
    assert data["monthly_budget"] == "15000.00"    # money comes back as an exact string


def test_duplicate_category_name_is_409(client, auth_headers):
    response = client.post("/categories", json={"name": "food"}, headers=auth_headers)
    assert response.status_code == 409             # "Food" already exists (case-insensitive)


def test_two_users_can_have_same_category_name(client, auth_headers, other_headers):
    response = client.post("/categories", json={"name": "Gym"}, headers=auth_headers)
    assert response.status_code == 201
    response = client.post("/categories", json={"name": "Gym"}, headers=other_headers)
    assert response.status_code == 201


def test_patch_only_changes_sent_fields(client, auth_headers, category_ids):
    food = category_ids["Food"]
    response = client.patch(f"/categories/{food}", json={"monthly_budget": "5000"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Food"
    assert response.json()["monthly_budget"] == "5000.00"


def test_patch_name_null_is_422(client, auth_headers, category_ids):
    response = client.patch(f"/categories/{category_ids['Food']}", json={"name": None}, headers=auth_headers)
    assert response.status_code == 422


def test_other_users_category_is_404(client, auth_headers, other_headers, category_ids):
    food = category_ids["Food"]
    assert client.get(f"/categories/{food}", headers=other_headers).status_code == 404
    assert client.delete(f"/categories/{food}", headers=other_headers).status_code == 404


def test_delete_category_keeps_its_expenses(client, auth_headers, category_ids, add_expense):
    food = category_ids["Food"]
    expense = add_expense(category_id=food)

    assert client.delete(f"/categories/{food}", headers=auth_headers).status_code == 204
    assert client.get(f"/categories/{food}", headers=auth_headers).status_code == 404

    response = client.get(f"/expenses/{expense['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["category"] is None     # now uncategorised
