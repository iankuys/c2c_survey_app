import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

# Starting with any number of alphanumeric characters (and '.', '+', '_', '-')
#   followed by a single '@'
#   followed by any number of alphanumeric characters (and '.', '_', '-')
#   followed by a single '.'
#   ending with any number of letters
EMAIL_REGEX = re.compile(r"^[A-Za-z0-9\.\+_-]+@[A-Za-z0-9\._-]+\.[a-zA-Z]*$")


def timestamp_now(compact=False, only_ymd=False) -> str:
    """Returns a string of the current date+time in the form of
        YYYY-MM-DD hh:mm:ss
    If `compact` == True, then returns in the form of
        YYYYMMDD_hhmmss
    If `only_ymd` == True, then only the first "year/month/day" portion is returned:
        YYYY-MM-DD or YYYYMMDD
    """
    timestamp = datetime.now()
    if compact:
        if only_ymd:
            return timestamp.strftime("%Y%m%d")
        return timestamp.strftime("%Y%m%d_%H%M%S")
    if only_ymd:
        return timestamp.strftime("%Y-%m-%d")
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def create_readable_timestamp(compact_timestamp: str, minutes_to_add: int = 0) -> str:
    """Transforms a compact timestamp from the format "YYYYMMDD_hhmmss" to a more human-readable format.
    Example output: Oct 04, 2022 04:02:23 PM
    Optionally adds a specified amount of minutes (`minutes_to_add`) to the returned string.
    """
    time_object = datetime.strptime(compact_timestamp, "%Y%m%d_%H%M%S") + timedelta(
        minutes=minutes_to_add
    )
    return time_object.strftime("%b %d, %Y %I:%M:%S %p")


def json_to_dict(
    path_to_json_file: Path | str,
    required_fields: set[str] = set(),
    only_required_fields: bool = False,
) -> dict:
    """Loads a json file into a dict.
    The `required_fields` parameter accepts a set of strings containing JSON keys that are expected to be present
    in the JSON file and populated.
        If this argument is provided, an error will be raised if any keys from this set are missing in this JSON
        file.
    If `only_required_fields` is True, an error will raised if any extra fields are found that are _not_ in
    `required_fields`.
    """
    if type(path_to_json_file) == str:
        path_to_json_file = Path(path_to_json_file)
    if not path_to_json_file.exists() or not path_to_json_file.is_file():
        raise FileNotFoundError(f"JSON file not found: '{path_to_json_file}'")
    result = dict()
    with open(path_to_json_file) as infile:
        result = json.load(infile)
    if only_required_fields:
        for loaded_field in result:
            if loaded_field not in required_fields:
                raise ValueError(
                    f"JSON file '{path_to_json_file.resolve()}'\nUnexpected field '{loaded_field}'"
                )
    for field in required_fields:
        if field not in result or result[field] == "":
            raise ValueError(
                f"JSON file '{path_to_json_file.resolve()}'\nField '{field}' is missing or empty"
            )
    return result


def timed(func):
    """Decorator to display function execution time."""

    def get_time(*args, **kwargs):
        time_pre = time.perf_counter()

        val = func(*args, **kwargs)

        time_post = time.perf_counter()
        final_time = time_post - time_pre
        print(
            f"[ {func.__name__}() completed in {final_time:0.4f}s{'' if final_time < 60 else f' ({final_time/60:0.2f} min)'} ]"
        )
        return val

    return get_time


def is_valid_email_address(email_address: str) -> bool:
    return bool(EMAIL_REGEX.match(email_address))


def remove_duplicates_and_preserve_order(input_list: list) -> list:
    # https://stackoverflow.com/a/17016257
    # Leverages Python dicts now being ordered by default
    return list(dict.fromkeys(input_list))
