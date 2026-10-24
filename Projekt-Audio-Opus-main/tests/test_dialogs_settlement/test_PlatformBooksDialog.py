from GUI.Widgets.Dialogs.PlatformBooksDialog import book_is_on_platform


def test_matches_platform_from_product_streaming_list_case_insensitively():
    product = {"streaming": ["Legimi", "Storytel"]}

    assert book_is_on_platform(product, "storytel")
    assert book_is_on_platform(product, " LEGIMI ")


def test_does_not_match_book_from_another_platform():
    assert not book_is_on_platform({"streaming": ["Legimi"]}, "Storytel")
    assert not book_is_on_platform({}, "Storytel")
