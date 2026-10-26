def test_home_page_serves_the_website(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Kharcha" in response.text


def test_static_files_are_served(client):
    assert client.get("/static/js/app.js").status_code == 200
    assert client.get("/static/css/style.css").status_code == 200
