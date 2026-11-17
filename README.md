# Лабораторна №8 — продуктивність, NumPy і профілювання

Версія коду: **1.0.0**. Новий `NumpyScorer` у `src/findex/numpy_rank.py` використовує
постинги NumPy `int32`, векторні формули TF-IDF/BM25, частковий відбір
порогового значення через `np.partition`, а при однакових балах сортування за doc_id.
У CLI: `findex search index.bin "python" --engine numpy`.
В API: `GET /search?q=python&engine=numpy`.

## Запуск і перевірки

```bash
git switch main
git pull origin main
python -m pip install -e .
python -m pip install pytest
python scripts/generate_demo_corpus.py
findex index data/demo --out index.bin
findex search index.bin "python" --engine numpy
python -m pytest tests/test_numpy_lab08.py -v
python -m pytest
python scripts/benchmark_lab08.py index.bin --query "python AND пошук AND документ"
```

Скрипт створить `benchmarks/lab08/results.json`, `search.prof`, `profile.txt`.
Профіль через `cProfile` — лише базова частина завдання; для повного звіту
слід зробити також py-spy flame graph, а три найгарячіші місця описати **за фактичними
вимірюваннями**.

## Дані вимірювань

| Запит | Python BM25, мс | NumPy BM25, мс | Прискорення |
|---|---:|---:|---:|
| Частий | виміряти | виміряти | виміряти |
| Рідкісний | виміряти | виміряти | виміряти |
| Три терміни | виміряти | виміряти | виміряти |

Результати не вигадані: цей бенчмарк потрібно виконати у Codespaces.
Додайте `pytest-benchmark` до CI, щоб бачити регресії часу.

## Пошукова система: data flow

```text
корпус -> iter_documents -> tokenize -> інвертований індекс
                              -> Scorer / NumpyScorer
                              -> CLI / FastAPI -> HTML-сторінка
```

## Reflection

- NumPy переносить обчислювальні цикли на векторні операції, але створення масивів
  і виклики бібліотеки мають накладні витрати: на коротких постингах може бути повільніше.
- Процеси з лаби 5 допомагають CPU-bound обробці, а async із лаби 6 — очікуванню I/O.
- Семантичний пошук із embeddings / RRF **ще не реалізовано**; це необов'язковий
  шлях, але натомість для повного завдання потрібен окремий дослід стискання постингів
  або mmap зі збільшеним корпусом та замірами пам'яті.
- Публічний URL, відеодемо, GIF, py-spy, complete benchmark і теги
  `lab-08` / `v1.0.0` ще не підтверджені.

Попередні лабораторні залишаються в тому самому репозиторії.
