from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("aliasgraph")
except PackageNotFoundError:  # editable install in some test contexts
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
