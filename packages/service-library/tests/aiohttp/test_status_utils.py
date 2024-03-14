from http import HTTPStatus

import pytest
from servicelib.aiohttp import status
from servicelib.aiohttp.web_exceptions_extension import collect_aiohttp_http_exceptions
from servicelib.status_utils import (
    _INVALID_STATUS_CODE_MSG,
    get_code_description,
    get_code_display_name,
    get_http_status_codes,
    is_client_error,
    is_error,
    is_informational,
    is_redirect,
    is_server_error,
    is_success,
)


def test_display():
    assert get_code_display_name(status.HTTP_200_OK) == "HTTP_200_OK"
    assert get_code_display_name(status.HTTP_306_RESERVED) == "HTTP_306_RESERVED"
    assert get_code_display_name(11) == _INVALID_STATUS_CODE_MSG


def test_description():
    # SEE https://github.com/python/cpython/blob/main/Lib/http/__init__.py#L54-L171
    assert (
        get_code_description(status.HTTP_200_OK)
        == "Request fulfilled, document follows. See https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/200"
    )


def test_status_codes_checks():

    assert is_informational(status.HTTP_102_PROCESSING)
    assert is_success(status.HTTP_202_ACCEPTED)
    assert is_redirect(status.HTTP_301_MOVED_PERMANENTLY)

    assert is_client_error(status.HTTP_401_UNAUTHORIZED)
    assert is_server_error(status.HTTP_503_SERVICE_UNAVAILABLE)

    assert is_error(status.HTTP_401_UNAUTHORIZED)
    assert is_error(status.HTTP_503_SERVICE_UNAVAILABLE)


def test_predicates_with_status():

    # in formational
    assert get_http_status_codes(status, is_informational) == [
        status.HTTP_100_CONTINUE,
        status.HTTP_101_SWITCHING_PROTOCOLS,
        status.HTTP_102_PROCESSING,
        status.HTTP_103_EARLY_HINTS,
    ]

    # errors
    assert [is_error(c) for c in get_http_status_codes(status, is_error)]

    # all. Curiously 306 is not in HTTPSTatus!
    assert [
        HTTPStatus(c)
        for c in get_http_status_codes(status)
        if c != status.HTTP_306_RESERVED
    ]


AIOHTTP_EXCEPTION_CLASSES_MAP = collect_aiohttp_http_exceptions()


codes_without_aiohttp_exception_class = (
    status.HTTP_100_CONTINUE,
    status.HTTP_101_SWITCHING_PROTOCOLS,
    status.HTTP_102_PROCESSING,
    status.HTTP_103_EARLY_HINTS,
    status.HTTP_207_MULTI_STATUS,
    status.HTTP_208_ALREADY_REPORTED,
    status.HTTP_226_IM_USED,
    status.HTTP_306_RESERVED,
    status.HTTP_418_IM_A_TEAPOT,
    status.HTTP_423_LOCKED,
    status.HTTP_424_FAILED_DEPENDENCY,
    status.HTTP_508_LOOP_DETECTED,
)


@pytest.mark.parametrize("status_code", get_http_status_codes(status))
def test_most_status_codes_map_to_one_aiohttp_exception_class(status_code):

    aiohttp_exception_cls = AIOHTTP_EXCEPTION_CLASSES_MAP.get(status_code)
    assert aiohttp_exception_cls is not None
