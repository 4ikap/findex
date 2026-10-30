import argparse
import pickle
import tracemalloc
from pathlib import Path
from typing import List, Set, Dict
from findex.index import Posting, DocMeta, build_inverted_index


# --- Движок 1: Two-Pointer Merge ---

def merge_intersect(p1: List[Posting], p2: List[Posting]) -> List[Posting]:
    result = []
    i, j = 0, 0
    while i < len(p1) and j < len(p2):
        if p1[i].doc_id == p2[j].doc_id:
            result.append(p1[i])
            i += 1
            j += 1
        elif p1[i].doc_id < p2[j].doc_id:
            i += 1
        else:
            j += 1
    return result


def merge_union(p1: List[Posting], p2: List[Posting]) -> List[Posting]:
    result = []
    i, j = 0, 0
    while i < len(p1) and j < len(p2):
        if p1[i].doc_id == p2[j].doc_id:
            result.append(p1[i])
            i += 1
            j += 1
        elif p1[i].doc_id < p2[j].doc_id:
            result.append(p1[i])
            i += 1
        else:
            result.append(p2[j])
            j += 1
    result.extend(p1[i:])
    result.extend(p2[j:])
    return result


def merge_not(p1: List[Posting], p2: List[Posting]) -> List[Posting]:
    exclude = {p.doc_id for p in p2}
    return [p for p in p1 if p.doc_id not in exclude]


# --- Движок 2: Python Set ---

def set_intersect(p1: List[Posting], p2: List[Posting]) -> Set[str]:
    return {p.doc_id for p in p1}.intersection(p.doc_id for p in p2)


def set_union(p1: List[Posting], p2: List[Posting]) -> Set[str]:
    return {p.doc_id for p in p1}.union(p.doc_id for p in p2)


def set_not(p1: List[Posting], p2: List[Posting]) -> Set[str]:
    return {p.doc_id for p in p1}.difference(p.doc_id for p in p2)


# --- Пошуковий процесор ---

def execute_query(query: str, index: Dict[str, List[Posting]], engine: str = "merge") -> Set[str]:
    """
    Простий парсер та виконавець булевих запитів (підтримує терміни через AND, OR, NOT).
    Приклад запиту: "python AND code", "data NOT test"
    """
    parts = query.strip().split()
    if not parts:
        return set()

    # Простий розбір по черзі (термін оператор термін)
    term1 = parts[0]
    postings1 = index.get(term1.lower(), [])

    if len(parts) == 1:
        return {p.doc_id for p in postings1} if engine == "set" else postings1

    op = parts[1].upper()
    term2 = parts[2] if len(parts) > 2 else ""
    postings2 = index.get(term2.lower(), []) if term2 else []

    if engine == "merge":
        if op == "AND":
            res = merge_intersect(postings1, postings2)
        elif op == "OR":
            res = merge_union(postings1, postings2)
        elif op == "NOT":
            res = merge_not(postings1, postings2)
        else:
            res = postings1
        return {p.doc_id for p in res}
    else:  # set engine
        if op == "AND":
            return set_intersect(postings1, postings2)
        elif op == "OR":
            return set_union(postings1, postings2)
        elif op == "NOT":
            return set_not(postings1, postings2)
        else:
            return {p.doc_id for p in postings1}


# --- УВАГА БЕЗПЕКИ PICKLE ---
# Завантаження файлів pickle (`pickle.load`) з ненадійних джерел є критично небезпечним,
# оскільки під час десеріалізації бібліотека може виконати довільний домішок коду (RCE),
# закладений у байт-коді злочинцем. Використовувати pickle лише для власних локальних даних.


def save_index(index, meta, path: Path):
    with open(path, "wb") as f:
        pickle.dump({"index": index, "meta": meta}, f)


def load_index(path: Path):
    with open(path, "rb") as f:
        data = pickle.load(f)
    return data["index"], data["meta"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Findex Search CLI")
    parser.add_argument("index_file", type=Path, help="Шлях до файлу індексу (.bin)")
    parser.add_argument("query", type=str, help="Пошуковий запит (наприклад: ' слово AND слово ')")
    parser.add_argument("--engine", choices=["merge", "set"], default="merge", help="Вибір пошукового движка")

    args = parser.parse_args()

    # Заміри пам'яті через tracemalloc
    tracemalloc.start()

    print(f"Завантаження індексу з {args.index_file}...")
    index, meta = load_index(args.index_file)

    print(f"Виконання пошуку ('{args.query}') через движок [{args.engine}]...")
    results = execute_query(args.query, index, engine=args.engine)

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"\nЗнайдено збігів: {len(results)}")
    print(f"Пік споживання пам'яті: {peak / 1024 / 1024:.2f} MB")





#python -m findex.search index.bin "the" --engine merge      команду пошуку

#python -m findex.search index.bin "the AND and" --engine merge    виконання булевого пошуку