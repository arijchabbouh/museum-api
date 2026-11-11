import uuid

from flask import Flask, jsonify, request

app = Flask(__name__)
museums = {}
visits = []
POINTS_PER_VISIT = 10
BADGES = [(10, "gold"), (5, "silver"), (3, "bronze")]


def text(data, key, max_len=100):
    value = str(data.get(key, "")).strip()
    return value if 0 < len(value) <= max_len else ""


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.get("/museums")
def list_museums():
    return jsonify(list(museums.values()))


@app.post("/museums")
def create_museum():
    data = request.get_json(silent=True) or {}
    name, theme, artist = text(data, "name"), text(data, "theme"), text(data, "artist", 50)
    if not name or not theme or not artist:
        return jsonify(error="'name', 'theme' and 'artist' are required"), 400
    museum = {"id": str(uuid.uuid4()), "name": name, "theme": theme, "artist": artist}
    museums[museum["id"]] = museum
    return jsonify(museum), 201


@app.get("/museums/<museum_id>")
def get_museum(museum_id):
    museum = museums.get(museum_id)
    if museum is None:
        return jsonify(error="museum not found"), 404
    return jsonify(museum)


@app.get("/artists/<artist>/museums")
def get_museums_by_artist(artist):
    own = [m for m in museums.values() if m["artist"].lower() == artist.lower()]
    return jsonify(own)


@app.post("/visits")
def create_visit():
    data = request.get_json(silent=True) or {}
    visitor = text(data, "visitor", 50)
    museum = museums.get(text(data, "museum_id"))
    if not visitor or not museum:
        return jsonify(error="'visitor' and a valid 'museum_id' are required"), 400
    already = any(v["visitor"].lower() == visitor.lower() and v["museum_id"] == museum["id"] for v in visits)
    is_owner = visitor.lower() == museum["artist"].lower()
    points = 0 if already or is_owner else POINTS_PER_VISIT
    visit = {"visitor": visitor, "museum_id": museum["id"], "artist": museum["artist"], "points": points}
    visits.append(visit)
    return jsonify(visit), 201


def artist_profile(name):
    received = [v for v in visits if v["artist"].lower() == name.lower()]
    scoring = [v for v in received if v["points"] > 0]
    badge = next((b for n, b in BADGES if len(scoring) >= n), None)
    return {"artist": name, "visits": len(received), "points": sum(v["points"] for v in received), "badge": badge}


@app.get("/artists/<artist>")
def get_artist(artist):
    return jsonify(artist_profile(artist))


@app.get("/leaderboard")
def leaderboard():
    names = {m["artist"] for m in museums.values()}
    board = sorted((artist_profile(n) for n in names), key=lambda p: p["points"], reverse=True)
    return jsonify(board[:10])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)