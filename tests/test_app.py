import pytest

from app.main import app, museums, visits


@pytest.fixture
def client():
    museums.clear()
    visits.clear()
    return app.test_client() 

def new_museum(client, artist="arij"):
    body = {"name": "Pixel Dreams", "theme": "retro", "artist": artist}
    return client.post("/museums", json=body).json["id"]

def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json == {"status": "ok"}

def test_first_visit_gives_points(client):
    mid = new_museum(client)
    response = client.post("/visits", json={"visitor": "nour", "museum_id": mid})
    assert response.status_code == 201
    assert response.json["points"] == 10

def test_create_museum(client):
    response = client.post("/museums", json={"name": "Pixel Dreams", "theme": "retro", "artist": "arij"})
    assert response.status_code == 201
    assert response.json["name"] == "Pixel Dreams"
    assert response.json["theme"] == "retro"
    assert response.json["artist"] == "arij"

def test_create_museum_missing_field(client):
    response = client.post("/museums", json={"name": "Pixel Dreams", "theme": "retro"})
    assert response.status_code == 400
    assert "error" in response.json

def test_get_unkown_museum(client):
    response = client.get("/museums/unknown")
    assert response.status_code == 404
    assert "error" in response.json

def test_artist_museums(client):
    new_museum(client, artist="arij")
    new_museum(client, artist="arij")
    new_museum(client, artist="nour")
    response = client.get("/artists/arij/museums")
    assert response.status_code == 200
    assert len(response.json) == 2

def test_repeat_visit_gives_no_points(client):
    mu=new_museum(client)
    client.post("/visits", json={"visitor": "nour", "museum_id": mu})
    response = client.post("/visits" ,json={"visitor": "nour", "museum_id":mu})
    assert response.status_code == 201
    assert response.json["points"] == 0

def test_self_visit_gives_no_points(client):
    mu=new_museum(client, artist="nour")
    response = client.post("/visits" ,json={"visitor": "nour", "museum_id":mu})
    assert response.status_code == 201
    assert response.json["points"] == 0

def test_bronze_badge(client):
    mu=new_museum(client, artist="nour")
    for i in range(3):
        client.post("/visits", json={"visitor": f"visitor{i}", "museum_id": mu})
    response = client.get("/artists/nour")
    assert response.status_code == 200
    assert response.json["badge"] == "bronze"

def test_leaderboard_order(client):
    mu1=new_museum(client, artist="arij")
    mu2=new_museum(client, artist="nour")
    client.post("/visits", json={"visitor": "visitor1", "museum_id": mu1})
    client.post("/visits", json={"visitor": "visitor2", "museum_id": mu1})
    client.post("/visits", json={"visitor": "visitor3", "museum_id": mu2})
    response = client.get("/leaderboard")
    assert response.status_code == 200
    assert response.json[0]["artist"] == "arij"
    assert response.json[1]["artist"] == "nour"

