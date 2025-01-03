from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import get_type_hints
from zoneinfo import ZoneInfo

import dateutil.parser


@dataclass
class HometaxModel:
    def __setattr__(self, key, value):
        super().__setattr__(key, convert_field_type(get_type_hints(self.__class__)[key], value))


def convert_field_type(to_type, value):
    if value is None:
        return value

    if (to_type, type(value)) in hometax_field_mapping:
        return hometax_field_mapping[to_type, type(value)](to_type, value)

    if isinstance(to_type, type) and not isinstance(value, to_type):
        return to_type(value)

    return value


hometax_field_mapping = {
    (date, str): lambda to_type, value: parse_date(value),
    (datetime, str): lambda to_type, value: dateutil.parser.parse(value).replace(tzinfo=ZoneInfo('Asia/Seoul')),
    (Enum, str): lambda to_type, value: to_type(value),
    (Enum, Enum): lambda to_type, value: value,
}


def parse_date(value: str) -> date:
    if len(value) == 6:
        value += '01'
    return dateutil.parser.parse(value).date()