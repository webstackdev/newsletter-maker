from types import SimpleNamespace

from core.views import _check_database, _check_qdrant


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


def test_check_database_returns_true_when_query_succeeds(mocker):
    cursor = mocker.Mock()
    cursor_cm = mocker.MagicMock()
    cursor_cm.__enter__.return_value = cursor
    mocker.patch("core.views.connection.cursor", return_value=cursor_cm)

    assert _check_database() is True
    cursor.execute.assert_called_once_with("SELECT 1")
    cursor.fetchone.assert_called_once_with()


def test_check_database_returns_false_when_query_raises(mocker):
    mocker.patch("core.views.connection.cursor", side_effect=RuntimeError("db unavailable"))

    assert _check_database() is False


def test_check_qdrant_returns_true_when_client_can_list_collections(mocker, settings):
    client_cls = mocker.patch("core.views.QdrantClient")
    client_cls.return_value.get_collections.return_value = SimpleNamespace(collections=[])

    assert _check_qdrant() is True
    client_cls.assert_called_once_with(url=settings.QDRANT_URL, timeout=2, check_compatibility=False)


def test_check_qdrant_returns_false_when_client_errors(mocker):
    client_cls = mocker.patch("core.views.QdrantClient")
    client_cls.return_value.get_collections.side_effect = RuntimeError("qdrant unavailable")

    assert _check_qdrant() is False
