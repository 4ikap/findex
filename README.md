# Лабораторна №7 — FastAPI, Pydantic і публічна адреса

Версія пакета — **0.7.0**. Вебсервер реалізовано в `src/findex/web/`.
Маршрути: `GET /` (HTML/Jinja2), `GET /search` (`q`, `scorer`, `page`),
`GET /docs/{doc_id}` (вміст документа), `GET /stats`, `GET /health`.
У `lifespan` індекс один раз читається з файлу, який визначає `INDEX_PATH`.
Якщо файлу немає, `/health` повертає 503. Вхід/вихід API перевіряється
Pydantic, старі dataclass-моделі індексу залишено.

## Локальний запуск у Codespaces

```bash
git switch main
git pull origin main
python -m pip install -e .
python -m pip install pytest
python scripts/generate_demo_corpus.py
findex index data/demo --out index.bin
export INDEX_PATH="$PWD/index.bin"
findex serve --port 8000 --workers 1
```

Відкрий вкладку **Ports** у Codespaces, зроби порт **8000** публічним (лише якщо
маєш право оприлюднювати документи), скопіюй URL і перевір `/health`.
GitHub Codespaces може засинати: для постійної адреси потрібен Render/Fly/Railway
чи інший хостинг. **Публічна адреса поки не налаштована**, тому не вигадана.

## API

```bash
curl 'http://localhost:8000/health'
curl 'http://localhost:8000/stats'
curl --get 'http://localhost:8000/search' --data-urlencode 'q=python' --data 'page=1'
```

У разі відсутнього параметра або некоректного запиту повертається 422.
Відсутній `doc_id` повертає 404. Результати ранжуються стабільно, мають
сніпети та посторінкову навігацію. CLI `findex serve --port 8000 --workers 1`
запускає Uvicorn.

## Тести

```bash
python -m pytest tests/test_web_lab07.py -v
python -m pytest
```

TestClient із dependency_overrides перевіряє пошук, 422, 404, 503 та HTML
без окремого файлового індексу. **Тести у Codespaces ще потрібно виконати.**

## Docker

```bash
docker build -t findex:0.7.0 .
docker run --rm -p 8000:8000 -v "$PWD/index.bin:/app/data/index.bin:ro" findex:0.7.0
```

Dockerfile використовує builder-етап і непривілейованого користувача.
Потрібно окремо перевірити збірку Docker у твоєму середовищі.

## Навантажувальні вимірювання

Потрібно виміряти **20 одночасних запитів** для sync та async реалізацій
на локальному і розгорнутому сервері, для 1 та 4 воркерів:
p50, p95, p99. Цих експериментів ще **не виконано** — не підставляй
вигадані цифри.

| Середовище | Route | Workers | p50 (мс) | p95 (мс) | p99 (мс) |
|---|---|---:|---:|---:|---:|
| Local | def | 1 | виміряти | виміряти | виміряти |
| Local | async def | 1 | виміряти | виміряти | виміряти |
| Deployed | def | 4 | виміряти | виміряти | виміряти |
| Deployed | async def | 4 | виміряти | виміряти | виміряти |

## Reflection

- **GIL:** CPU-bound пошук не стає паралельним від самого `async def`;
  блокуюча робота в event loop гальмує всі корутини.
- **Thread pool:** FastAPI запускає синхронні `def`-маршрути у пулі потоків.
- **Кілька процесів:** `--workers` створює окремі процеси, кожен завантажує
  свою копію індексу, тому збільшується витрата пам'яті.
- **Pydantic:** перевіряє типи й обмеження параметрів на HTTP-межі.

**Для повної здачі:** перевірити тести, зробити sync/async бенчмарки,
опублікувати живу адресу на початку README, отримати віддалені p50/p95/p99
та створити тег `lab-07`. Теги попередніх робіт не змінюються.


## Lab 07 — HTTP load measurements

Use the included `scripts/benchmark_lab07.py` to collect **actual** p50/p95/p99 for
20 concurrent clients. The sync `/search` endpoint is a normal `def` route,
and `/search-async` is an `async def` route which offloads synchronous search
and file I/O into the threadpool; this avoids blocking the event loop, but does
not magically bypass Python's GIL for CPU-bound ranking.

```bash
# From a fresh Codespaces shell
python -m pip install -e .
export INDEX_PATH="$PWD/index.bin"
findex serve --port 8000 --workers 1
# In a separate terminal:
python scripts/benchmark_lab07.py http://127.0.0.1:8000 --route /search
python scripts/benchmark_lab07.py http://127.0.0.1:8000 --route /search-async
# Repeat with --workers 4, restarting the server, and with deployed HTTPS URL.
```

Measurements are appended to `benchmarks/lab07/results.jsonl`; copy the real
p50/p95/p99 into the performance table. **No deployment URL or actual latency
measurements are available yet.** Do not treat Codespaces preview URLs as
permanently hosted production services. Do not publish sensitive documents.
