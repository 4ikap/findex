# Findex — Лабораторна робота 4: типи, тести, пакування і CLI

![CI](https://github.com/4ikap/findex/actions/workflows/ci.yml/badge.svg)

`findex` — інвертований індекс і ранжований пошук (TF-IDF / BM25) над корпусом `.bz2`. У цій лабораторній він стає справжнім Python-пакетом: суворі типи (pyright strict), 173 тести з покриттям 100%, команда `findex` у PATH, логування замість `print`, CI і реліз із wheel.

**Корпус:** `fiction.tokenized.shuffled.txt.bz2` — 1 811 548 документів (кожен рядок — окремий документ), 652 839 термінів, 17 507 648 постінгів.

---

## 📦 Встановлення

```bash
# як інструмент (findex потрапляє в PATH):
uv tool install .
# або з wheel із GitHub Release:
uv tool install https://github.com/4ikap/findex/releases/download/v0.4.0/findex-0.4.0-py3-none-any.whl

# для розробки (залежності + група dev):
uv sync
```

Перевірено на Windows (Python 3.15.2): wheel `findex-0.4.0-py3-none-any.whl` ставиться в **чисте оточення** (`uv venv` + `uv pip install`), там працюють `findex --version` (`findex 0.4.0`) і `findex --help`; `uv tool install .` кладе `findex.exe` у PATH, і він запускається з будь-якого каталогу.

---

## 🖥 CLI

```text
Usage: findex [OPTIONS] COMMAND [ARGS]...

 Findex: інвертований індекс і ранжований пошук (TF-IDF / BM25).

Options:
  --version        Показати версію й вийти
  --help           Show this message and exit.

Commands:
  index   Будує інвертований індекс із корпусу й зберігає його у файл.
  search  Ранжований пошук: таблиця результатів (або JSON зі --json).
  stats   Статистика індексу: розміри, довжина документів, найчастіші терміни.
```

### `findex index` — індексація зі смугою прогресу (rich)

```bash
findex index data --out index.bin --positions
```

Опції: `--out/-o` (файл індексу), `--format/-f pickle|json`, `--positions/--no-positions` (позиції потрібні для фраз у лапках). Смуга прогресу рахується за прочитаними стиснутими байтами корпусу і пишеться в **stderr**, щоб stdout лишався чистим.

### `findex search` — таблиця результатів або JSON

```bash
findex search index.bin "дощ AND (ніч OR вечір) NOT сніг" --data data -k 5 -v
```

```text
                               Результати: дощ AND (ніч OR вечір) NOT сніг (bm25)
┌───┬─────────┬─────────────────────────────────────────────────┬───────────────────────────────────────────────┐
│ # │     Бал │ Документ                                        │ Сніпет                                        │
├───┼─────────┼─────────────────────────────────────────────────┼───────────────────────────────────────────────┤
│ 1 │ 20.2927 │ fiction.tokenized.shuffled.txt.bz2_line_1169055 │ Ніч дощ                                       │
│ 2 │ 18.9768 │ fiction.tokenized.shuffled.txt.bz2_line_1723323 │ Ніч темна дощ                                 │
│ 3 │ 16.7981 │ fiction.tokenized.shuffled.txt.bz2_line_1030724 │ Ніч і теплий липкий дощ                       │
│ 4 │ 15.8862 │ fiction.tokenized.shuffled.txt.bz2_line_1248639 │ Падав дощ ніч чорна мов вугіль                │
│ 5 │ 15.0682 │ fiction.tokenized.shuffled.txt.bz2_line_1188171 │ Темніська ніч укладалась а дощ лляв неустанно │
└───┴─────────┴─────────────────────────────────────────────────┴───────────────────────────────────────────────┘
```

У терміналі терми у сніпеті підсвічені жовтим. Опції: `--scorer/-s bm25|tfidf`, `--top/-k`, `--data/-d` (папка з корпусом для сніпетів), `--json`, `-v/-vv`.

**`--json`** пише дані в stdout (їх можна перенаправити у файл чи в `jq`), а діагностика йде в stderr:

```bash
findex search index.bin '"темна ніч"' --json -k 3 --data data
```

```json
{
  "query": "\"темна ніч\"",
  "scorer": "bm25",
  "results": [
    {"rank": 1, "score": 21.195719996527437, "doc_id": "fiction.tokenized.shuffled.txt.bz2_line_968582", "snippet": "Темна ніч"},
    {"rank": 2, "score": 19.82121613245861, "doc_id": "fiction.tokenized.shuffled.txt.bz2_line_1570012", "snippet": "Була темна ніч"},
    {"rank": 3, "score": 19.82121613245861, "doc_id": "fiction.tokenized.shuffled.txt.bz2_line_32916", "snippet": "Була темна ніч"}
  ]
}
```

(У файлі відповідь форматована з відступами; тут рядки стиснуто для читабельності.)

### `findex stats` — статистика індексу

```bash
findex stats index.bin --top 8
```

```text
             Індекс index.bin
┌───────────────────────────┬────────────┐
│ Терміни                   │    652,839 │
│ Документи                 │  1,811,548 │
│ Середня довжина документа │      10.16 │
│ Усього постінгів          │ 17,507,648 │
│ Позиції збережено         │        так │
└───────────────────────────┴────────────┘
Топ-8 термінів за df
┌────────┬─────────┐
│ Термін │      df │
├────────┼─────────┤
│ і      │ 393,185 │
│ не     │ 334,184 │
│ на     │ 283,974 │
│ в      │ 246,553 │
│ а      │ 225,598 │
│ що     │ 224,222 │
│ з      │ 211,464 │
│ й      │ 201,700 │
└────────┴─────────┘
```

### Помилки: один рядок і ненульовий код виходу

Очікувані помилки (немає файлу індексу, зламаний запит, пошкоджений індекс, фраза без позицій, недоступний вихідний файл) — це `FindexError` та `OSError`. CLI показує **один рядок** у stderr і виходить з кодом 1, без стека викликів:

```text
$ findex search nope.bin дощ
Помилка: Файл індексу не знайдено: nope.bin        (код виходу 1)

$ findex search index.bin "(дощ"
Помилка: Відсутня закриваюча дужка )               (код виходу 1)
```

Синтаксис запиту перевіряється **до** завантаження індексу: зламаний запит падає миттєво, а не після ~60 с завантаження.

---

## 🧾 Логування замість `print`

- Усі діагностичні `print` замінено на `logging`: попередження про пошкоджені `.bz2`-файли й дублікати `doc_id`, `[timed]`, `[cache] HIT/MISS`.
- Логер налаштовується **один раз** — у точці входу CLI (`configure_logging`): handler пише в **stderr**, рівень залежить від `-v`: за замовчуванням `WARNING`, `-v` — `INFO`, `-vv` — `DEBUG`.
- Звіт-скрипти лаб 1–2 (`stats.py`, `greedy_stats.py`, `benchmark.py`) лишили `print`: їхній вивід і є результатом (звіт у stdout), а не діагностика.

```text
$ findex search index.bin "дощ AND (ніч OR вечір) NOT сніг" --data data -k 5 -v      (stderr)
INFO findex: [timed] load_index: 59726.12 ms
INFO findex: [cache] MISS 'дощ AND (ніч OR вечір) NOT сніг'
INFO findex: [timed] SearchEngine.search: 320.98 ms
```

---

## 🏷 Типи: pyright strict

`pyproject.toml` містить `typeCheckingMode = "strict"` для `src/findex`; результат `pyright`: **0 помилок, 0 попереджень**. У `src` немає жодного `# type: ignore`; у тестах їх п'ять, і кожен має коментар, навіщо він (перевірка поведінки на навмисно хибних аргументах: `None` у токенізатор, невідомий формат, невідомий `scorer`, присвоєння frozen-dataclass).

- **`Scorer` — `typing.Protocol`** (`@runtime_checkable`): `TfIdf` і `BM25` нічого не наслідують, pyright перевіряє їх структурно, а `isinstance(scorer, Scorer)` працює й у тестах.
- **`Literal`** для рядкових параметрів: `ScorerName = Literal["bm25", "tfidf"]`, `IndexFormat = Literal["pickle", "json"]`, `engine: Literal["merge", "set"]`. У CLI ці ж варіанти подано як `StrEnum` (його розуміє typer і показує як `<bm25|tfidf>`), а потім відображено на `Literal`.
- **Генератори** — `Iterator[...]` (`tokenize`, `iter_documents`), `Generator[Index, None, None]` для `@contextmanager`.
- **Декоратори** `@timed` та `@_handle_errors` — узагальнені через ParamSpec (`def timed[**P, R](...)`), тому зберігають сигнатуру обгорнутої функції.
- `Index` — `Mapping[str, list[Posting]]`.

Що знайшов pyright на першому проході (9 помилок), і як це виправлено:
- `Scorer.score` приймав структурний протокол `CorpusStats` із `@property avg_doc_length`, а `Index.avg_doc_length` — `cached_property`; pyright вважає їх несумісними. Тепер `score` приймає `Index` напряму.
- `@contextmanager` з `-> Iterator[Index]` застарілий (`reportDeprecated`) → `Generator[Index, None, None]`.

> Локально на Windows `pyright.exe` блокувала політика Application Control (os error 4551), тому перевірка запускалась як `uv run python -m pyright`; на GitHub Actions це не потрібно.

---

## 🧪 Тести (pytest + Hypothesis)

**173 тести** (172 швидкі + 1 `slow`), усі проходять. Швидкий набір — `pytest -m "not slow"` — виконується за ~1,3 с.

| Файл | Тестів | Що перевіряє |
| :--- | :--- | :--- |
| `test_tokenizer.py` | 15 | `parametrize`: українська (апострофи `'` і `’`, `ї/є/ґ`), цифри, емодзі, дефіси, порожній ввід; NFD = NFC; лінивість; `None` |
| `test_core.py` | 12 | читання `.bz2`, порядок, порожні рядки, пошкоджений файл (лог), колбек прогресу, `read_document` |
| `test_index.py` | 25 | протокол `Mapping`, `cached_property`, збірка на маленькому корпусі (`conftest.py`), `save/load` (pickle і JSON), `open_index` при винятку, помилки формату |
| `test_merge.py` | 17 | `merge_*` проти `set_*` (parametrize), `execute_query` для обох движків |
| `test_query.py` | 36 | **порівняння дерев** (не рядків), оператори `&`, `\|`, `~`, синтаксичні помилки, `evaluate`, фрази |
| `test_scoring.py` | 15 | три перевірки рейтингу з лаби 3 для **обох** скорерів, протокол без наслідування, `make_scorer` |
| `test_search.py` | 18 | ранжування, топ-k, кеш (`HIT/MISS` у логу), сніпети, precision@k |
| `test_properties.py` | 5 | **Hypothesis** (нижче) |
| `test_cli.py` | 25 | `typer.testing.CliRunner`: `index`, `search` (таблиця, `--json`), `stats`, `-v/-vv`, помилки |
| `test_sanity.py` | 2 | markdown-звіт трьох перевірок рейтингу |
| `test_package.py` | 2 | версія пакета та запасне значення |
| `test_slow.py` | 1 | **`@pytest.mark.slow`**: індекс із 60 000 документів і пошук (~4 с) |

**Властивості Hypothesis** (їх п'ять, вимога — щонайменше три):
1. `load(save(index))` дає той самий індекс (pickle і JSON, з позиціями й без);
2. постінги завжди відсортовані за `doc_id`, без дублікатів, `freq == len(positions)`, а сума `freq` дорівнює сумі довжин документів;
3. `merge_intersect / merge_union / merge_not` збігаються з операціями над `set`;
4. бал рейтингу не спадає, коли зростає `tf`;
5. токенізатор стабільний: повторна токенізація власного виводу нічого не змінює.

Запуск: `uv run pytest` (усі), `uv run pytest -m "not slow"` (швидкі), `uv run pytest --cov` (з покриттям).

### Покриття: 100%

`pytest --cov` (з `branch = true`): **100%** — 733 інструкції, 194 гілки, 0 пропущених (виміряно на Windows, Python 3.15.2).

**Навмисно поза покриттям:**
- `benchmark.py`, `stats.py`, `greedy_stats.py` — звіт-скрипти лаб 1–2 з виводом у stdout, перевіряються запуском вручну; виключено через `omit`;
- `__main__.py` — один виклик `app()` (також у `omit`);
- рядки `if __name__ == "__main__"` та `raise NotImplementedError` у тілах базових методів (`exclude_also`).

**Чого покриття не гарантує:** 100% — це про виконані рядки, а не про коректність. Не перевірялось автотестами: відмальовування смуги прогресу в реальному терміналі (CliRunner не є tty), `findex index` на повному корпусі (1,8 млн документів; вручну, ~5–6 хв), а також самі workflow GitHub Actions (їх перевіряє сам CI).

---

## 🔧 Пакування (`pyproject.toml` + uv)

- Метадані, залежності (`typer`, `rich`) і група `dev` (`pytest`, `pytest-cov`, `hypothesis`, `ruff`, `pyright`).
- `[project.scripts] findex = "findex.cli:app"` — команда `findex`.
- `requires-python = ">=3.12"`; `uv.lock` закомічено, у CI його перевіряє `uv sync --locked`.
- `ruff check .` — без зауважень; налаштування `ruff`, `pytest`, `coverage` і `pyright` — у `pyproject.toml`.

---

## ⚙️ CI та реліз (GitHub Actions)

**`ci.yml`** — на кожен `push` і `pull_request`, матриця Python 3.12 і 3.13: `uv sync --locked` → `ruff check` → `pyright` → `pytest --cov`. Бейдж CI — угорі README.

**`release.yml`** — на тег `v*`: збирає wheel (`uv build --wheel`), перевіряє його в чистому оточенні (`findex --version`, `findex --help`) і створює GitHub Release із прикріпленим `findex-0.4.0-py3-none-any.whl`.

Релізи: `v0.4.0` (wheel у GitHub Release) та тег здачі `lab-04`.

---

## 🤔 Ключові рішення та обмеження

**Чому `Scorer` — Protocol, а не абстрактний клас?** Реалізації не залежать від базового класу, а pyright усе одно перевіряє `score(...)` структурно. Додаткова вигода — `@runtime_checkable` дозволяє `isinstance` у тестах.

**Чому `Scorer.score` приймає `Index`, а не власний протокол?** Спочатку я описав мінімальний протокол `CorpusStats` (`num_docs`, `avg_doc_length`), але pyright strict відхилив `Index`: `cached_property` не збігається з `@property` у протоколі. Простіший і чесніший варіант — прийняти сам `Index`.

**Чому `Literal`, а в CLI `StrEnum`?** `Literal` ловить неіснуючий `scorer` або `engine` статично. Typer будує вибір опцій з `Enum`, тому в CLI використано `StrEnum`, а на межі він відображається на `Literal`.

**Чому дані в stdout, а діагностика й прогрес у stderr?** Щоб `findex search ... --json > out.json` і `| jq` завжди отримували чистий JSON, а логи й смуга прогресу не змішувались із результатом (це перевіряє тест `test_search_json_goes_to_stdout_and_is_valid`).

**Чому запит парситься до завантаження індексу?** Індекс завантажується ~60 с; помилка в запиті має спливати одразу.

**Чому `uv sync --locked` у CI?** Якщо `pyproject.toml` змінили, а `uv.lock` — ні, CI падає, а не мовчки ставить інші версії.

**Чому pyright strict лише для `src`?** Тести навмисно перевіряють хибні аргументи; суворі типи для всіх фікстур і `parametrize` дали б багато шуму без користі.

**Обмеження:** індекс із позиціями потребує ~5,4 ГБ пам'яті при побудові й ~60 с на завантаження; оператори запиту — лише великими літерами; прогрес рахується за стиснутими байтами, тож він наближений; CLI-тести не перевіряють відмальовування rich у справжньому терміналі.
