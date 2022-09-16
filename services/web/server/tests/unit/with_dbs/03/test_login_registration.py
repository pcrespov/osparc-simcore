# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from unittest.mock import Mock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from pytest_simcore.helpers.utils_assert import assert_error, assert_status
from pytest_simcore.helpers.utils_login import NewInvitation, NewUser, parse_link
from servicelib.aiohttp.rest_responses import unwrap_envelope
from simcore_service_webserver.db_models import ConfirmationAction, UserStatus
from simcore_service_webserver.login._confirmation import _url_for_confirmation
from simcore_service_webserver.login.registration import get_confirmation_info
from simcore_service_webserver.login.settings import (
    LoginOptions,
    LoginSettings,
    get_plugin_options,
)
from simcore_service_webserver.login.storage import AsyncpgStorage, get_plugin_storage

EMAIL, PASSWORD = "tester@test.com", "password"


@pytest.fixture
def client(
    event_loop: asyncio.AbstractEventLoop,
    aiohttp_client,
    web_server: TestServer,
    mock_orphaned_services,
) -> TestClient:
    cli = event_loop.run_until_complete(aiohttp_client(web_server))
    return cli


@pytest.fixture
def cfg(client: TestClient) -> LoginOptions:
    assert client.app
    cfg = get_plugin_options(client.app)
    assert cfg
    return cfg


@pytest.fixture
def db(client: TestClient) -> AsyncpgStorage:
    assert client.app
    db: AsyncpgStorage = get_plugin_storage(client.app)
    assert db
    return db


async def test_regitration_availibility(client: TestClient):
    assert client.app
    url = client.app.router["auth_register"].url_for()
    r = await client.post(
        f"{url}",
        json={
            "email": EMAIL,
            "password": PASSWORD,
            "confirm": PASSWORD,
        },
    )

    await assert_status(r, web.HTTPOk)


async def test_regitration_is_not_get(client: TestClient):
    assert client.app
    url = client.app.router["auth_register"].url_for()
    r = await client.get(f"{url}")
    await assert_error(r, web.HTTPMethodNotAllowed)


async def test_registration_with_existing_email(client: TestClient, cfg: LoginOptions):
    assert client.app
    url = client.app.router["auth_register"].url_for()
    async with NewUser(app=client.app) as user:
        r = await client.post(
            f"{url}",
            json={
                "email": user["email"],
                "password": user["raw_password"],
                "confirm": user["raw_password"],
            },
        )
    await assert_error(r, web.HTTPConflict, cfg.MSG_EMAIL_EXISTS)


@pytest.mark.skip("TODO: Feature still not implemented")
async def test_registration_with_expired_confirmation(
    client: TestClient,
    cfg: LoginOptions,
    db: AsyncpgStorage,
    mocker: Mock,
):
    assert client.app
    mocker.patch(
        "simcore_service_webserver.login.settings.get_plugin_settings",
        return_value=LoginSettings(
            LOGIN_REGISTRATION_CONFIRMATION_REQUIRED=True,
            LOGIN_REGISTRATION_INVITATION_REQUIRED=True,
            LOGIN_TWILIO=None,
        ),
    )

    url = client.app.router["auth_register"].url_for()

    async with NewUser({"status": UserStatus.CONFIRMATION_PENDING.name}) as user:
        confirmation = await db.create_confirmation(
            user, ConfirmationAction.REGISTRATION.name
        )
        r = await client.post(
            f"{url}",
            json={
                "email": user["email"],
                "password": user["raw_password"],
                "confirm": user["raw_password"],
            },
        )
        await db.delete_confirmation(confirmation)

    await assert_error(r, web.HTTPConflict, cfg.MSG_EMAIL_EXISTS)


async def test_registration_with_invalid_confirmation_code(
    client: TestClient,
    cfg: LoginOptions,
    db: AsyncpgStorage,
    mocker: Mock,
):
    # Checks bug in https://github.com/ITISFoundation/osparc-simcore/pull/3356
    assert client.app
    mocker.patch(
        "simcore_service_webserver.login.settings.get_plugin_settings",
        return_value=LoginSettings(
            LOGIN_REGISTRATION_CONFIRMATION_REQUIRED=True,
            LOGIN_REGISTRATION_INVITATION_REQUIRED=False,
            LOGIN_TWILIO=None,
        ),
    )

    confirmation_link = _url_for_confirmation(
        client.app, code="INVALID_CONFIRMATION_CODE"
    )
    r = await client.get(f"{confirmation_link}")

    # Invalid code redirect to root without any error to the login page
    #
    assert r.ok
    assert f"{r.url.relative()}" == cfg.LOGIN_REDIRECT
    assert r.history[0].status == web.HTTPFound.status_code


async def test_registration_without_confirmation(
    client: TestClient,
    cfg: LoginOptions,
    db: AsyncpgStorage,
    mocker: Mock,
):
    assert client.app
    mocker.patch(
        "simcore_service_webserver.login.handlers.get_plugin_settings",
        return_value=LoginSettings(
            LOGIN_REGISTRATION_CONFIRMATION_REQUIRED=False,
            LOGIN_REGISTRATION_INVITATION_REQUIRED=False,
            LOGIN_TWILIO=None,
        ),
    )

    url = client.app.router["auth_register"].url_for()
    r = await client.post(
        f"{url}", json={"email": EMAIL, "password": PASSWORD, "confirm": PASSWORD}
    )
    data, error = unwrap_envelope(await r.json())

    assert r.status == 200, (data, error)
    assert cfg.MSG_LOGGED_IN in data["message"]

    user = await db.get_user({"email": EMAIL})
    assert user
    await db.delete_user(user)


async def test_registration_with_confirmation(
    client: TestClient,
    cfg: LoginOptions,
    db: AsyncpgStorage,
    capsys,
    mocker,
):
    assert client.app
    mocker.patch(
        "simcore_service_webserver.login.handlers.get_plugin_settings",
        return_value=LoginSettings(
            LOGIN_REGISTRATION_CONFIRMATION_REQUIRED=True,
            LOGIN_REGISTRATION_INVITATION_REQUIRED=False,
            LOGIN_TWILIO=None,
        ),
    )

    url = client.app.router["auth_register"].url_for()
    r = await client.post(
        f"{url}", json={"email": EMAIL, "password": PASSWORD, "confirm": PASSWORD}
    )
    data, error = unwrap_envelope(await r.json())
    assert r.status == 200, (data, error)

    user = await db.get_user({"email": EMAIL})
    assert user["status"] == UserStatus.CONFIRMATION_PENDING.name

    assert "verification link" in data["message"]

    # retrieves sent link by email (see monkeypatch of email in conftest.py)
    out, _ = capsys.readouterr()
    confirmation_url = parse_link(out)
    assert "/auth/confirmation/" in str(confirmation_url)
    resp = await client.get(confirmation_url)
    text = await resp.text()

    assert (
        "This is a result of disable_static_webserver fixture for product OSPARC"
        in text
    )
    assert resp.status == 200

    # user is active
    user = await db.get_user({"email": EMAIL})
    assert user["status"] == UserStatus.ACTIVE.name

    # cleanup
    await db.delete_user(user)


@pytest.mark.parametrize(
    "is_invitation_required,has_valid_invitation,expected_response",
    [
        (True, True, web.HTTPOk),
        (True, False, web.HTTPForbidden),
        (False, True, web.HTTPOk),
        (False, False, web.HTTPOk),
    ],
)
async def test_registration_with_invitation(
    client: TestClient,
    cfg: LoginOptions,
    db: AsyncpgStorage,
    is_invitation_required: bool,
    has_valid_invitation: bool,
    expected_response: type[web.HTTPError],
    mocker: Mock,
):
    assert client.app
    mocker.patch(
        "simcore_service_webserver.login.handlers.get_plugin_settings",
        return_value=LoginSettings(
            LOGIN_REGISTRATION_CONFIRMATION_REQUIRED=False,
            LOGIN_REGISTRATION_INVITATION_REQUIRED=is_invitation_required,
            LOGIN_TWILIO=None,
        ),
    )

    #
    # User gets an email with a link as
    #   https:/some-web-address.io/#/registration/?invitation={code}
    #
    # Front end then creates the following request
    #
    async with NewInvitation(client) as confirmation:
        print(get_confirmation_info(cfg, confirmation))

        url = client.app.router["auth_register"].url_for()

        r = await client.post(
            f"{url}",
            json={
                "email": EMAIL,
                "password": PASSWORD,
                "confirm": PASSWORD,
                "invitation": confirmation["code"]
                if has_valid_invitation
                else "WRONG_CODE",
            },
        )
        await assert_status(r, expected_response)

        # check optional fields in body
        if not has_valid_invitation or not is_invitation_required:
            r = await client.post(
                f"{url}", json={"email": "new-user" + EMAIL, "password": PASSWORD}
            )
            await assert_status(r, expected_response)

        if is_invitation_required and has_valid_invitation:
            assert not await db.get_confirmation(confirmation)
