"""Production asset delivery avoids shipping uncompressed bundles."""

from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.settings import Settings


def test_static_text_assets_compress_without_changing_api_responses(tmp_path):
    web = tmp_path / "web"
    web.mkdir()
    web.joinpath("index.html").write_text("<html><body>App</body></html>")
    body = ".panel{color:blue;}\n" * 1000
    web.joinpath("app.css").write_text(body)
    settings = Settings(
        db_path=tmp_path / "db.sqlite3",
        data_dir=tmp_path / "data",
        spa_dist=web,
        auth="none",
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/app.css", headers={"Accept-Encoding": "gzip"})
        assert response.status_code == 200
        assert response.text == body
        assert response.headers.get("content-encoding") == "gzip"
        assert int(response.headers["content-length"]) < len(body) / 10
        assert client.get("/health").status_code == 200
