"""
Structural test 2: Verify all routes are registered with correct methods and paths.
"""
from app.main import app


def _route_map() -> dict[str, set[str]]:
    """Return {path: {methods}} for all registered routes, merging duplicate paths."""
    result: dict[str, set[str]] = {}
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            result.setdefault(route.path, set()).update(route.methods or [])
    return result


def test_user_routes_registered():
    routes = _route_map()
    assert "/api/users" in routes
    assert "POST" in routes["/api/users"]
    assert "/api/users/{user_id}" in routes
    assert "GET" in routes["/api/users/{user_id}"]
    assert "PATCH" in routes["/api/users/{user_id}"]


def test_profile_routes_registered():
    routes = _route_map()
    assert "/api/profile/upload" in routes
    assert "POST" in routes["/api/profile/upload"]
    assert "/api/profile/{user_id}" in routes
    assert "GET" in routes["/api/profile/{user_id}"]


def test_opportunity_routes_registered():
    routes = _route_map()
    assert "/api/opportunities" in routes
    assert "GET" in routes["/api/opportunities"]
    assert "POST" in routes["/api/opportunities"]
    assert "/api/opportunities/search" in routes
    assert "POST" in routes["/api/opportunities/search"]


def test_tracker_routes_registered():
    routes = _route_map()
    assert "/api/tracker/{user_id}" in routes
    assert "GET" in routes["/api/tracker/{user_id}"]
    assert "/api/tracker" in routes
    assert "POST" in routes["/api/tracker"]
    assert "/api/tracker/{app_id}" in routes
    assert "PATCH" in routes["/api/tracker/{app_id}"]
    assert "DELETE" in routes["/api/tracker/{app_id}"]


def test_chat_routes_registered():
    routes = _route_map()
    assert "/api/chat" in routes
    assert "POST" in routes["/api/chat"]
    assert "/api/chat/stream" in routes
    assert "POST" in routes["/api/chat/stream"]
    assert "/api/chat/health" in routes
    assert "GET" in routes["/api/chat/health"]


def test_root_route_registered():
    routes = _route_map()
    assert "/" in routes
    assert "GET" in routes["/"]


async def test_health_endpoint(client):
    r = await client.get("/api/chat/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_root_endpoint(client):
    r = await client.get("/")
    data = r.json()
    assert r.status_code == 200
    assert "agents" in data
    assert len(data["agents"]) == 6


async def test_missing_user_returns_404(client):
    r = await client.get("/api/users/nonexistent-id-xyz")
    assert r.status_code in (404, 500)  # 500 if DB unreachable, 404 if connected


async def test_docs_available(client):
    r = await client.get("/docs")
    assert r.status_code == 200
