def test_root_redirects_to_admin(client):
    response = client.get("/")

    assert response.status_code == 302
    assert response["Location"] == "/admin/"


def test_healthz_returns_ok(client):
    response = client.get("/healthz/")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readyz_returns_ok_when_dependencies_are_ready(client, mocker):
    mocker.patch("core.views._check_database", return_value=True)
    mocker.patch("core.views._check_qdrant", return_value=True)

    response = client.get("/readyz/")

    assert response.status_code == 200
    assert response.json()["checks"] == {"database": True, "qdrant": True}


def test_readyz_returns_service_unavailable_when_dependency_fails(client, mocker):
    mocker.patch("core.views._check_database", return_value=True)
    mocker.patch("core.views._check_qdrant", return_value=False)

    response = client.get("/readyz/")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
