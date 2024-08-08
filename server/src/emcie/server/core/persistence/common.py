from typing import Any, Callable, Literal, Mapping, NewType, TypedDict, Union, cast


ObjectId = NewType("ObjectId", str)


# Metadata Query Grammar
LiteralValue = Union[str, int, float, bool]
FieldName = str
WhereOperator = TypedDict(
    "WhereOperator",
    {
        "$gt": LiteralValue,
        "$gte": LiteralValue,
        "$lt": LiteralValue,
        "$lte": LiteralValue,
        "$ne": LiteralValue,
        "$eq": LiteralValue,
    },
    total=False,
)
WhereExpression = dict[FieldName, WhereOperator]

LogicalOperator = TypedDict(
    "LogicalOperator",
    {
        "$and": list[Union[WhereExpression, "LogicalOperator"]],
        "$or": list[Union[WhereExpression, "LogicalOperator"]],
    },
    total=False,
)
Where = Union[WhereExpression, LogicalOperator]

# {"id": {"$eq": "123"}}
# {"$and": [{"id": {"$eq": "123"}}, {"name": {"$eq": "moshe"}}]}


def evaluate_filter(
    operator: str,
    field_value: LiteralValue,
    filter_value: LiteralValue,
) -> bool:
    tests: dict[str, Callable[[Any, Any], bool]] = {
        "$eq": lambda field_value, filter_value: field_value == filter_value,
        "$ne": lambda field_value, filter_value: field_value != filter_value,
        "$gt": lambda field_value, filter_value: field_value > filter_value,
        "$gte": lambda field_value, filter_value: field_value >= filter_value,
        "$lt": lambda field_value, filter_value: field_value < filter_value,
        "$lte": lambda field_value, filter_value: field_value <= filter_value,
    }

    return tests[operator](field_value, filter_value)


def matches_filters(
    where: Where,
    candidate: Mapping[str, Any],
) -> bool:
    if not where:
        return True

    if next(iter(where.keys())) in ("$and", "$or"):
        op = cast(LogicalOperator, where)
        for operator in op:
            operands: list[Union[WhereExpression, LogicalOperator]] = op[
                cast(Literal["$and", "$or"], operator)
            ]
            if operator == "$and":
                if not all(matches_filters(sub_filter, candidate) for sub_filter in operands):
                    return False
            elif operator == "$or":
                if not any(matches_filters(sub_filter, candidate) for sub_filter in operands):
                    return False

    else:
        field_filters = cast(WhereExpression, where)
        for field_name, field_filter in field_filters.items():
            for operator, filter_value in field_filter.items():
                if not evaluate_filter(
                    operator, candidate[field_name], cast(LiteralValue, filter_value)
                ):
                    return False

    return True


class NoMatchingDocumentsError(Exception):
    def __init__(self, collection_name: str, filters: Where) -> None:
        super().__init__("No matching documents were found")
        self.collection_name = collection_name
        self.filters = filters
