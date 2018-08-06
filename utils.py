import statistics


def mean_or_zero(iter):
    try:
        return statistics.mean(iter)
    except statistics.StatisticsError:
        return 0


def parse_float(str):
    try:
        return float(str.replace(',', '').replace('%', ''))
    except (ValueError, AttributeError):
        return 0


def parse_int(str):
    try:
        return int(str.replace(',', ''))
    except (ValueError, AttributeError):
        return 0


def attr_or_key_getter(name, obj, default_value=0):
    try:
        return getattr(obj, name)
    except AttributeError:
        return obj.get(name, default_value)


def first_or_none(iter):
    try:
        return iter[0]
    except IndexError:
        return None


def float_or_none(x):
    return None if not x else float(x.replace(',', ''))
