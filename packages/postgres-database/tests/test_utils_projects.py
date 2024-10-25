# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any, AsyncIterator

import pytest
import sqlalchemy
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from faker import Faker
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.utils_projects import (
    DBProjectNotFoundError,
    ProjectsRepo,
)
from sqlalchemy.ext.asyncio import AsyncEngine


async def _delete_project(connection: SAConnection, project_uuid: uuid.UUID) -> None:
    result = await connection.execute(
        sqlalchemy.delete(projects).where(projects.c.uuid == f"{project_uuid}")
    )
    assert result.rowcount == 1


@pytest.fixture
async def registered_user(
    connection: SAConnection,
    create_fake_user: Callable[..., Awaitable[RowProxy]],
) -> RowProxy:
    user = await create_fake_user(connection)
    assert user
    return user


@pytest.fixture
async def registered_project(
    connection: SAConnection,
    registered_user: RowProxy,
    create_fake_project: Callable[..., Awaitable[RowProxy]],
) -> AsyncIterator[dict[str, Any]]:
    project = await create_fake_project(connection, registered_user)
    assert project

    yield dict(project)

    await _delete_project(connection, project["uuid"])


async def test_get_project_last_change_date(
    asyncpg_engine: AsyncEngine, registered_project: dict, faker: Faker
):
    projects_repo = ProjectsRepo(asyncpg_engine)

    project_last_change_date = await projects_repo.get_project_last_change_date(
        project_uuid=registered_project["uuid"]
    )
    assert isinstance(project_last_change_date, datetime)

    with pytest.raises(DBProjectNotFoundError):
        await projects_repo.get_project_last_change_date(
            project_uuid=faker.uuid4()  # <-- Non existing uuid in DB
        )