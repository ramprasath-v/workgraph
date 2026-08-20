import pytest

from catalog import ProductCatalog


def make_catalog() -> ProductCatalog:
    return ProductCatalog({"notebook": 1299, "pen": 250})


def test_initial_numeric_and_display_lookups():
    catalog = make_catalog()

    assert catalog.price_cents("notebook") == 1299
    assert catalog.display_price("notebook") == "$12.99"


def test_update_return_value_and_direct_lookup_are_preserved():
    catalog = make_catalog()

    assert catalog.update_price("notebook", 1499) == 1499
    assert catalog.price_cents("notebook") == 1499


def test_invalid_products_and_prices_are_rejected():
    catalog = make_catalog()

    with pytest.raises(KeyError):
        catalog.update_price("marker", 300)
    for invalid in (0, -1, True, 2.5):
        with pytest.raises(ValueError):
            catalog.update_price("pen", invalid)


def test_updating_one_product_preserves_another_product():
    catalog = make_catalog()

    catalog.update_price("notebook", 1499)

    assert catalog.price_cents("pen") == 250
    assert catalog.display_price("pen") == "$2.50"


def test_display_lookup_reflects_an_accepted_price_update():
    catalog = make_catalog()

    catalog.update_price("notebook", 1499)

    assert catalog.display_price("notebook") == "$14.99"


def test_catalog_rows_reflect_an_accepted_price_update():
    catalog = make_catalog()

    catalog.update_price("pen", 300)

    assert catalog.catalog_rows() == (
        ("notebook", "$12.99"),
        ("pen", "$3.00"),
    )
