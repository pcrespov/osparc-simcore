""" Basic diagnostic handles to the rest API for operations


"""
from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.rest_responses import wrap_as_envelope
from servicelib.rest_utils import body_to_dict, extract_and_validate

from . import __version__


async def check_health(request: web.Request):
    params, query, body = await extract_and_validate(request)

    assert not params
    assert not query
    assert not body

    data = {
        'name':__name__.split('.')[0],
        'version': __version__,
        'status': 'SERVICE_RUNNING',
        'api_version': __version__
    }

    return data


async def check_action(request: web.Request):
    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params
    assert query, "query %s" % query
    assert body, "body %s" % body

    if params['action'] == 'fail':
        raise ValueError("some randome failure")


    # echo's input
    data = {
        "path_value" : params.get('action'),
        "query_value": query.get('data'),
        "body_value" : body_to_dict(body)
    }

    return wrap_as_envelope(data=data)


async def get_config(request: web.Request):
    params, query, body = await extract_and_validate(request)

    assert not params
    assert not query
    assert not body

    cfg = request.app[APP_CONFIG_KEY]
    login_cfg = cfg.get('login',{})

    data = {
        'invitation_required': login_cfg.get('registration_invitation_required', False)
    }

    return data
