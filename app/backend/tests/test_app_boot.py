"""Boot smoke tests for the backend scaffold."""


def test_app_boots_and_exposes_openapi(client) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert (
        response.json()["info"]["title"] == "AI Collaborative Document Editor Backend"
    )
