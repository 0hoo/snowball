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


def attr_or_key_getter(name, obj):
    try:
        return getattr(obj, name)
    except AttributeError:
        return obj.get(name, 0)