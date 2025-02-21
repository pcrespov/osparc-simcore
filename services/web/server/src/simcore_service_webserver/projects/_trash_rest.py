import logging

from aiohttp import web
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)

from .._meta import API_VTAG as VTAG
from ..exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ..login.decorators import get_user_id, login_required
from ..products.products_service import get_product_name
from ..security.decorators import permission_required
from . import _trash_service
from ._common.exceptions_handlers import handle_plugin_requests_exceptions
from ._common.models import ProjectPathParams, RemoveQueryParams
from .exceptions import ProjectRunningConflictError, ProjectStoppingError

_logger = logging.getLogger(__name__)


_TRASH_ERRORS: ExceptionToHttpErrorMap = {
    ProjectRunningConflictError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        "Current study is in use and cannot be trashed [project_id={project_uuid}]. Please stop all services first and try again",
    ),
    ProjectStoppingError: HttpErrorInfo(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "Something went wrong while stopping services before trashing. Aborting trash.",
    ),
}

_handle_local_request_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TRASH_ERRORS)
)


routes = web.RouteTableDef()


@routes.post(f"/{VTAG}/projects/{{project_id}}:trash", name="trash_project")
@login_required
@permission_required("project.delete")
@handle_plugin_requests_exceptions
@_handle_local_request_exceptions
async def trash_project(request: web.Request):
    user_id = get_user_id(request)
    product_name = get_product_name(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)
    query_params: RemoveQueryParams = parse_request_query_parameters_as(
        RemoveQueryParams, request
    )

    await _trash_service.trash_project(
        request.app,
        product_name=product_name,
        user_id=user_id,
        project_id=path_params.project_id,
        force_stop_first=query_params.force,
        explicit=True,
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.post(f"/{VTAG}/projects/{{project_id}}:untrash", name="untrash_project")
@login_required
@permission_required("project.delete")
@handle_plugin_requests_exceptions
@_handle_local_request_exceptions
async def untrash_project(request: web.Request):
    user_id = get_user_id(request)
    product_name = get_product_name(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    await _trash_service.untrash_project(
        request.app,
        product_name=product_name,
        user_id=user_id,
        project_id=path_params.project_id,
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)
