from __future__ import annotations

from typing import Any

from . import form as _form


class RequestParameters(dict):
    """Hosts a dict with lists as values where get returns the first value of the list and getlist returns the whole shebang"""  # noqa: E501

    def get(self, name: str, default: Any | None = None) -> Any | None:
        """Return the first value, either the default or actual

        Args:
            name (str): The name of the parameter
            default (Any | None, optional): The default value. Defaults to None.

        Returns:
            Any | None: The first value of the list
        """  # noqa: E501
        return super().get(name, [default])[0]

    def getlist(
        self, name: str, default: list[Any] | None = None
    ) -> list[Any]:
        """Return the entire list

        Args:
            name (str): The name of the parameter
            default (list[Any] | None, optional): The default value. Defaults to None.

        Returns:
            list[Any]: The entire list of values or [] if not found
        """  # noqa: E501
        return super().get(name, default) or []

    def __getattr__(self, name: str) -> Any:
        """Return the first value, or ``""`` when missing.

        Mirrors the convenience attribute access already available on
        ``request.cookies`` and ``request.headers``. Trailing underscores
        are stripped so Python keywords (``class_``, ``from_``) can be
        used as attribute names. Underscores inside the name are kept
        as-is because form and query-string keys are typically written in
        ``snake_case``; use ``get``/``__getitem__`` for keys that contain
        characters not valid in a Python identifier.

        The first value is coerced to ``str`` to match the
        ``cookies``/``headers`` shape, except for :class:`File`
        instances (used by ``request.files``): those are returned
        unchanged so callers can reach ``.name``/``.body``/``.type``
        instead of the ``repr`` of the namedtuple.

        Args:
            name (str): The attribute name to look up as a parameter.

        Returns:
            The first value as a ``str``, an unwrapped :class:`File`
            when the value is an uploaded file, or ``""`` if the
            parameter is not present.
        """
        if name.startswith("_"):
            raise AttributeError(name)
        val = self.get(name.rstrip("_"), "")
        if isinstance(val, _form.File):
            return val
        return str(val)
