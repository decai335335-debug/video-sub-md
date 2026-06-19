from core.douyin.extractor import extract_video_id, is_douyin_url, normalize_url


def test_douyin_modal_url_normalizes_to_video_url():
    url = "https://www.douyin.com/jingxuan?modal_id=7632664889143627059"

    assert is_douyin_url(url)
    assert extract_video_id(url) == "7632664889143627059"
    assert normalize_url(url) == "https://www.douyin.com/video/7632664889143627059"


def test_douyin_video_url_keeps_video_id():
    url = "https://www.douyin.com/video/7632664889143627059"

    assert is_douyin_url(url)
    assert extract_video_id(url) == "7632664889143627059"
    assert normalize_url(url) == url
