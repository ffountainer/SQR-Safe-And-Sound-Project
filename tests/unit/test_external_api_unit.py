import pytest

import src.external_api as external_api


def test_api_key_from_env_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(external_api.YANDEX_MAPS_API_KEY_ENV, "  test-key  ")
    assert external_api._api_key_from_env() == "test-key"


def test_api_key_from_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(external_api.YANDEX_MAPS_API_KEY_ENV, raising=False)
    with pytest.raises(ValueError, match="missing"):
        external_api._api_key_from_env()


def test_parse_first_point_success() -> None:
    data = {
        "response": {
            "GeoObjectCollection": {
                "featureMember": [
                    {"GeoObject": {"Point": {"pos": "49.1221 55.7887"}}}
                ]
            }
        }
    }
    assert external_api._parse_first_point(data) == (49.1221, 55.7887)


def test_parse_first_point_empty_results() -> None:
    data = {"response": {"GeoObjectCollection": {"featureMember": []}}}
    with pytest.raises(ValueError, match="no results"):
        external_api._parse_first_point(data)


def test_parse_first_point_unexpected_shape() -> None:
    with pytest.raises(ValueError, match="unexpected"):
        external_api._parse_first_point({"broken": "shape"})


def test_map_widget_url_contains_coordinates() -> None:
    url = external_api.map_widget_url(49.1, 55.7, zoom=14, lang="en_US")
    assert "map-widget" in url
    assert "ll=49.1%2C55.7" in url
    assert "z=14" in url
    assert "lang=en_US" in url


def test_map_widget_iframe_html_uses_geocode_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(external_api, "geocode_address", lambda _: (50.0, 60.0))

    html = external_api.map_widget_iframe_html("Innopolis", width=400, height=200, zoom=12)

    assert "<iframe" in html
    assert "width=\"400\"" in html
    assert "height=\"200\"" in html
    assert "ll=50.0%2C60.0" in html
