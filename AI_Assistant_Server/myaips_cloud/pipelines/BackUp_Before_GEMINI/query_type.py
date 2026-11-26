# app/pipelines/query_type.py

def detect_query_type(question: str) -> str:
    """
    Πολύ απλή αναγνώριση τύπου ερώτησης.
    Μπορείς να την βελτιώσεις όποτε θέλεις.
    """
    q = question.lower()

    if any(x in q for x in ["explain", "analysis", "why", "how"]):
        return "explanatory"

    if any(x in q for x in ["summarize", "summary", "συνοψ", "περίληψη"]):
        return "summary"

    if any(x in q for x in ["compare", "difference"]):
        return "comparison"

    if any(x in q for x in ["solve", "calculate", "υπολόγισε"]):
        return "technical"

    return "generic"


def get_store_weights(query_type: str):
    """
    Βάρη ανάλογα με το είδος της ερώτησης.
    Επιστρέφει (RAW_W, SUMMARY_W, ENTITY_W)
    - entity πλέον δεν το χρησιμοποιούμε, αλλά το αφήνουμε για συμβατότητα
    """
    if query_type == "summary":
        return (0.4, 1.0, 0.0)

    if query_type == "explanatory":
        return (0.8, 0.6, 0.0)

    if query_type == "comparison":
        return (0.7, 0.7, 0.0)

    if query_type == "technical":
        return (1.0, 0.5, 0.0)

    return (0.9, 0.6, 0.0)
