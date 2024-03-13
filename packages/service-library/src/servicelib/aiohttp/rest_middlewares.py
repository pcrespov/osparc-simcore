""" rest - middlewares for error, enveloping and validation

    SEE  https://gist.github.com/amitripshtos/854da3f4217e3441e8fceea85b0cbd91
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import Any, Union

from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import StreamResponse
from servicelib.error_codes import create_error_code
from servicelib.json_serialization import json_dumps

from ..mimetype_constants import MIMETYPE_APPLICATION_JSON
from ..utils import is_production_environ
from .rest_models import ErrorItem, LogMessage, ResponseErrorBody
from .rest_responses import (
    create_data_response,
    create_http_error,
    is_enveloped_from_map,
    is_enveloped_from_text,
    wrap_as_envelope,
)
from .rest_utils import EnvelopeFactory
from .typing_extension import Handler, Middleware

DEFAULT_API_VERSION = "v0"


_logger = logging.getLogger(__name__)


def is_api_request(request: web.Request, api_version: str) -> bool:
    base_path = "/" + api_version.lstrip("/")
    return bool(request.path.startswith(base_path))


def _handle_http_error(request: web.BaseRequest, err: web.HTTPError):
    """Ensures response for a web.HTTPError is complete"""
    assert request  # nosec

    # TODO: differenciate between server/client error
    if not err.reason:
        err.set_status(
            err.status_code,
            reason=HTTPStatus(err.status_code).phrase,
        )

    err.content_type = MIMETYPE_APPLICATION_JSON
    if not err.text or not is_enveloped_from_text(err.text):
        error = ResponseErrorBody(
            errors=[
                ErrorItem.from_error(err),
            ],
            status=err.status,
            logs=[
                LogMessage(message=err.reason, level="ERROR"),
            ],
            message=err.reason,
        )
        err.text = EnvelopeFactory(error=error).as_text()

    raise err


def _handle_http_successful(request: web.BaseRequest, err: web.HTTPSuccessful):
    """Ensures raised web.HTTPSuccessful responses are complete"""
    err.content_type = MIMETYPE_APPLICATION_JSON
    if err.text:
        try:
            payload = json.loads(err.text)
            if not is_enveloped_from_map(payload):
                payload = wrap_as_envelope(data=payload)
                err.text = json_dumps(payload)
        except Exception as other_error:  # pylint: disable=broad-except
            _handle_as_internal_server_error(request, other_error)
    raise err


def _handle_as_internal_server_error(request: web.BaseRequest, err: Exception):
    """
    This error handler is the last resource to catch unhandled exceptions and
    are converted into web.HTTPInternalServerError (i.e. 500)

    Its purpose is:
        - respond the client with 500 and a reference OEC
        - log sufficient information to diagnose the issue
    """
    error_code = create_error_code(err)
    resp = create_error_response(
        err,
        reason=f"Ups, something went wrong. We took note [{error_code}]",
        http_error_cls=web.HTTPInternalServerError,
        skip_internal_error_details=True,
    )
    _logger.exception(
        "Unexpected '%s' for %s [%s]\n%s",
        type(err),
        f"'{request.method} {request.path}'",
        error_code,
        f"{request.remote=}, {request.headers=}",
        extra={"error_code": error_code},
    )
    raise resp


def error_middleware_factory(
    api_version: str,
) -> Middleware:
    _is_prod: bool = is_production_environ()

    @web.middleware
    async def _middleware_handler(request: web.Request, handler: Handler):
        """
        Ensure all error raised are properly enveloped and json responses
        """
        if not is_api_request(request, api_version):
            return await handler(request)

        # FIXME: review when to send info to client and when not!
        try:
            return await handler(request)

        except web.HTTPError as err:
            _handle_http_error(request, err)

        except web.HTTPSuccessful as err:
            _handle_http_successful(request, err)

        except web.HTTPRedirection as err:
            _logger.debug("Redirected to %s", err)
            raise

        except NotImplementedError as err:
            http_error = create_http_error(
                err,
                http_error_cls=web.HTTPNotImplemented,
                skip_internal_error_details=_is_prod,
            )
            raise http_error from err

        except asyncio.TimeoutError as err:
            http_error = create_http_error(
                err,
                http_error_cls=web.HTTPGatewayTimeout,
                skip_internal_error_details=_is_prod,
            )
            raise http_error from err

        except Exception as err:  # pylint: disable=broad-except
            _handle_as_internal_server_error(request, err)

    # adds identifier (mostly for debugging)
    setattr(  # noqa: B010
        _middleware_handler, "__middleware_name__", f"{__name__}.error_{api_version}"
    )

    return _middleware_handler


_ResponseOrBodyData = Union[StreamResponse, Any]
HandlerFlexible = Callable[[Request], Awaitable[_ResponseOrBodyData]]
MiddlewareFlexible = Callable[[Request, HandlerFlexible], Awaitable[StreamResponse]]


def envelope_middleware_factory(api_version: str) -> MiddlewareFlexible:
    # FIXME: This data conversion is very error-prone. Use decorators instead!
    _is_prod: bool = is_production_environ()

    @web.middleware
    async def _middleware_handler(
        request: web.Request, handler: HandlerFlexible
    ) -> StreamResponse:
        """
        Ensures all responses are enveloped as {'data': .. , 'error', ...} in json
        ONLY for API-requests
        """
        if not is_api_request(request, api_version):
            resp = await handler(request)
            assert isinstance(resp, StreamResponse)  # nosec
            return resp

        # NOTE: the return values of this handler
        resp = await handler(request)

        if isinstance(resp, web.FileResponse):
            return resp

        if not isinstance(resp, StreamResponse):
            resp = create_data_response(
                data=resp,
                skip_internal_error_details=_is_prod,
            )

        assert isinstance(resp, web.StreamResponse)  # nosec
        return resp

    # adds identifier (mostly for debugging)
    setattr(  # noqa: B010
        _middleware_handler, "__middleware_name__", f"{__name__}.envelope_{api_version}"
    )

    return _middleware_handler


def append_rest_middlewares(
    app: web.Application, api_version: str = DEFAULT_API_VERSION
):
    """Helper that appends rest-middlewares in the correct order"""
    app.middlewares.append(error_middleware_factory(api_version))
    app.middlewares.append(envelope_middleware_factory(api_version))  # type: ignore[arg-type]
