def deep_flatten(arr):
    """
    Μετατρέπει arbitrarily nested lists σε flat list.
    Π.χ. [[a], [[b, c]], d] → [a, b, c, d]
    """
    result = []

    if isinstance(arr, list):
        for item in arr:
            result.extend(deep_flatten(item))
    else:
        result.append(arr)

    return result
