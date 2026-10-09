import base64

import pytest

from gallery.security import is_image_url, is_web_url


def test_allows_existing_inline_png_logo():
    value = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n").decode()

    assert is_image_url(value)
    assert not is_web_url(value)


@pytest.mark.parametrize("value", ["data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=", "data:image/png;base64,aGVsbG8=", "javascript:alert(1)", "https://example.com\\evil", "https://example.com\n"])
def test_rejects_unsafe_or_mislabeled_image_urls(value):
    assert not is_image_url(value)
