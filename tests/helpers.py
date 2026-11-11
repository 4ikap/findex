from findex.index import DocMeta, Index, Posting


def make_index() -> Index:
    """Маленький індекс із позиціями.

    d1: python async python code        (4 токени)
    d2: python await java               (3)
    d3: event loop python               (3)
    d4: code code code code event loop  (6)
    """
    docs = {
        "d1": ["python", "async", "python", "code"],
        "d2": ["python", "await", "java"],
        "d3": ["event", "loop", "python"],
        "d4": ["code", "code", "code", "code", "event", "loop"],
    }
    raw: dict = {}
    for doc_id, tokens in docs.items():
        for pos, token in enumerate(tokens):
            raw.setdefault(token, {}).setdefault(doc_id, []).append(pos)
    postings = {
        term: [Posting(d, len(pl), tuple(pl)) for d, pl in sorted(by_doc.items())]
        for term, by_doc in raw.items()
    }
    meta = {d: DocMeta(d, len(t)) for d, t in docs.items()}
    return Index(postings, meta, has_positions=True)
