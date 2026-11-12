from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("findex")
except PackageNotFoundError:  # пакет запущено з вихідників без встановлення
    __version__ = "0+unknown"
