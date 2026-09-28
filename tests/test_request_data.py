import random

import pytest

from sanic.cookies.request import CookieRequestParameters
from sanic.request.parameters import RequestParameters
from sanic.response import json


try:
    from ujson import loads
except ImportError:
    from json import loads


def test_custom_context(app):
    @app.middleware("request")
    def store(request):
        request.ctx.user = "sanic"
        request.ctx.session = None

    @app.route("/")
    def handler(request):
        # Accessing non-existent key should fail with AttributeError
        try:
            invalid = request.ctx.missing
        except AttributeError as e:
            invalid = str(e)
        return json(
            {
                "user": request.ctx.user,
                "session": request.ctx.session,
                "has_user": hasattr(request.ctx, "user"),
                "has_session": hasattr(request.ctx, "session"),
                "has_missing": hasattr(request.ctx, "missing"),
                "invalid": invalid,
            }
        )

    @app.middleware("response")
    def modify(request, response):
        # Using response-middleware to access request ctx
        try:
            user = request.ctx.user
        except AttributeError as e:
            user = str(e)
        try:
            invalid = request.ctx.missing
        except AttributeError as e:
            invalid = str(e)

        j = loads(response.body)
        j["response_mw_valid"] = user
        j["response_mw_invalid"] = invalid
        return json(j)

    request, response = app.test_client.get("/")
    assert response.json == {
        "user": "sanic",
        "session": None,
        "has_user": True,
        "has_session": True,
        "has_missing": False,
        "invalid": "'types.SimpleNamespace' object has no attribute 'missing'",
        "response_mw_valid": "sanic",
        "response_mw_invalid": "'types.SimpleNamespace' object has no"
        " attribute 'missing'",
    }


def test_app_injection(app):
    expected = random.choice(range(0, 100))

    @app.listener("after_server_start")
    async def inject_data(app, loop):
        app.ctx.injected = expected

    @app.get("/")
    async def handler(request):
        return json({"injected": request.app.ctx.injected})

    request, response = app.test_client.get("/")

    response_json = loads(response.text)
    assert response_json["injected"] == expected


# ---------------------------------------------------------------------------
# Attribute access on RequestParameters (issue #3192)
# ---------------------------------------------------------------------------


class TestRequestParametersAttrAccess:
    """``request.form``/``request.args``/``request.files`` support
    convenience attribute access matching the shape offered by
    ``request.cookies`` and ``request.headers``: return the first value
    coerced to ``str``, or ``""`` when the key is missing.
    """

    def test_first_value_as_string(self):
        params = RequestParameters({"user_id": ["42", "43"]})
        assert params.user_id == "42"

    def test_missing_returns_empty_string(self):
        params = RequestParameters({"present": ["x"]})
        assert params.missing == ""

    def test_trailing_underscore_stripped_for_python_keywords(self):
        params = RequestParameters({"class": ["math101"], "from": ["home"]})
        assert params.class_ == "math101"
        assert params.from_ == "home"

    def test_internal_underscore_kept_as_literal(self):
        """Form and query keys are typically snake_case, unlike cookies
        or headers which are kebab-case. The attribute name must be
        looked up verbatim (except for stripped trailing underscores)
        so a form field literally named ``user_id`` is reachable as
        ``.user_id`` instead of being rewritten to ``user-id``.
        """
        params = RequestParameters({"user_id": ["42"]})
        assert params.user_id == "42"
        params_hyphenated = RequestParameters({"user-id": ["42"]})
        assert params_hyphenated.user_id == ""

    def test_non_string_value_coerced_to_string(self):
        params = RequestParameters({"count": [7]})
        assert params.count == "7"

    def test_underscore_prefixed_attribute_raises(self):
        """Private/dunder lookups must fall through so ``copy``/``pickle``
        and other stdlib machinery keep working on the dict subclass.
        """
        params = RequestParameters({"x": ["1"]})
        with pytest.raises(AttributeError):
            params.__nonexistent_dunder__  # noqa: B018

    def test_existing_methods_take_precedence(self):
        params = RequestParameters({"get": ["shadow"]})
        # ``.get`` still resolves to the method, not a shadowed key.
        assert callable(params.get)
        # But the key is still reachable via subscript / .get():
        assert params["get"] == ["shadow"]
        assert params.get("get") == "shadow"

    def test_cookie_subclass_override_still_wins(self):
        """CookieRequestParameters defines its own ``__getattr__`` with
        kebab-case rewriting for HTTP cookie semantics. The subclass
        override must continue to take precedence over the base one
        introduced here.
        """
        cookies = CookieRequestParameters({"session-token": ["abc"]})
        # ``.session_token`` looks up ``session-token`` via the cookie
        # override's underscore-to-hyphen rewrite.
        assert cookies.session_token == "abc"
        # And a literal ``session_token`` cookie is NOT reachable via
        # attribute access on the cookie class (existing behaviour).
        cookies_literal = CookieRequestParameters({"session_token": ["abc"]})
        assert cookies_literal.session_token == ""


def test_form_attribute_access(app):
    @app.route("/", methods=["POST"])
    async def handler(request):
        return json(
            {
                "user_id": request.form.user_id,
                "class_": request.form.class_,
                "missing": request.form.missing,
            }
        )

    payload = "user_id=42&class=math101"
    headers = {"content-type": "application/x-www-form-urlencoded"}
    _, response = app.test_client.post("/", data=payload, headers=headers)
    assert response.json == {
        "user_id": "42",
        "class_": "math101",
        "missing": "",
    }


def test_args_attribute_access(app):
    @app.route("/", methods=["GET"])
    async def handler(request):
        return json(
            {
                "page": request.args.page,
                "sort_by": request.args.sort_by,
                "missing": request.args.missing,
            }
        )

    _, response = app.test_client.get("/?page=3&sort_by=name")
    assert response.json == {
        "page": "3",
        "sort_by": "name",
        "missing": "",
    }
