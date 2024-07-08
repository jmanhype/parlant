from emcie.server.core.persistence import FieldFilter, _matches_filters


def test_equal_to() -> None:
    field_filters = {"age": FieldFilter(equal_to=30)}
    candidate = {"age": 30}
    assert _matches_filters(field_filters, candidate)


def test_not_equal_to() -> None:
    field_filters = {"age": FieldFilter(not_equal_to=40)}
    candidate = {"age": 30}
    assert _matches_filters(field_filters, candidate)


def test_greater_than_true() -> None:
    field_filters = {"age": FieldFilter(greater_than=25)}
    candidate = {"age": 30}
    assert _matches_filters(field_filters, candidate)


def test_greater_than_false() -> None:
    field_filters = {"age": FieldFilter(greater_than=35)}
    candidate = {"age": 30}
    assert not _matches_filters(field_filters, candidate)


def test_greater_than_or_equal_to_true() -> None:
    candidate = {"age": 30}

    field_filters = {"age": FieldFilter(greater_than_or_equal_to=30)}
    assert _matches_filters(field_filters, candidate)

    field_filters = {"age": FieldFilter(greater_than_or_equal_to=29)}
    assert _matches_filters(field_filters, candidate)


def test_greater_than_or_equal_to_false() -> None:
    candidate = {"age": 30}

    field_filters = {"age": FieldFilter(greater_than_or_equal_to=31)}
    assert not _matches_filters(field_filters, candidate)


def test_less_than_true() -> None:
    field_filters = {"age": FieldFilter(less_than=35)}
    candidate = {"age": 30}
    assert _matches_filters(field_filters, candidate)


def test_less_than_false() -> None:
    field_filters = {"age": FieldFilter(less_than=25)}
    candidate = {"age": 30}
    assert not _matches_filters(field_filters, candidate)


def test_less_than_or_equal_to_true() -> None:
    candidate = {"age": 30}

    field_filters = {"age": FieldFilter(less_than_or_equal_to=30)}
    assert _matches_filters(field_filters, candidate)

    field_filters = {"age": FieldFilter(less_than_or_equal_to=31)}
    assert _matches_filters(field_filters, candidate)


def test_less_than_or_equal_to_false() -> None:
    field_filters = {"age": FieldFilter(less_than_or_equal_to=29)}
    candidate = {"age": 30}
    assert not _matches_filters(field_filters, candidate)


def test_regex_true() -> None:
    field_filters = {"name": FieldFilter(regex="^J")}
    candidate = {"name": "John"}
    assert _matches_filters(field_filters, candidate)


def test_regex_false() -> None:
    field_filters = {"name": FieldFilter(regex="^J")}
    candidate = {"name": "Mike"}
    assert not _matches_filters(field_filters, candidate)
