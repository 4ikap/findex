import tracemalloc
from array import array
from dataclasses import dataclass


# 1. Звичайний dataclass
@dataclass(frozen=True)
class NormalPosting:
    doc_id: str
    freq: int


# 2. Dataclass із slots
@dataclass(frozen=True, slots=True)
class SlottedPosting:
    doc_id: str
    freq: int


def run_memory_benchmark() -> None:
    """Порівнює пам'ять трьох варіантів зберігання 500 000 постінгів (Лаб 2)."""
    print("=== БЕНЧМАРК ПАМ'ЯТІ ДЛЯ ТРЬОХ ВАРІАНТІВ ПОСТІНГІВ ===")

    # Варіант 1: звичайний dataclass
    tracemalloc.start()
    normal_list = [NormalPosting(doc_id=f"doc_{i}", freq=1) for i in range(500_000)]
    _, peak_normal = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    del normal_list

    # Варіант 2: slots=True
    tracemalloc.start()
    slotted_list = [SlottedPosting(doc_id=f"doc_{i}", freq=1) for i in range(500_000)]
    _, peak_slotted = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    del slotted_list

    # Варіант 3: array('I') (числа для doc_id та freq)
    tracemalloc.start()
    doc_ids_array = array("I", range(500_000))
    freqs_array = array("I", [1] * 500_000)
    _, peak_array = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    del doc_ids_array, freqs_array

    print(f"1. Звичайний dataclass (500k об'єктів): {peak_normal / 1024 / 1024:.2f} MB")
    print(f"2. Dataclass з slots=True (500k об'єктів): {peak_slotted / 1024 / 1024:.2f} MB")
    print(f"3. Масиви array('I') (500k елементів): {peak_array / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    run_memory_benchmark()
