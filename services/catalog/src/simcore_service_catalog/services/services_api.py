import logging

from models_library.api_schemas_catalog.services import (
    MyServiceGet,
    ServiceGetV2,
    ServiceItemList,
    ServiceUpdateV2,
)
from models_library.groups import GroupID
from models_library.products import ProductName
from models_library.rest_pagination import PageLimitInt
from models_library.services_access import ServiceGroupAccessRightsV2
from models_library.services_history import Compatibility, ServiceRelease
from models_library.services_metadata_published import ServiceMetaDataPublished
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import HttpUrl, NonNegativeInt
from servicelib.rabbitmq.rpc_interfaces.catalog.errors import (
    CatalogForbiddenError,
    CatalogItemNotFoundError,
)
from simcore_service_catalog.db.repositories.groups import GroupsRepository

from ..db.repositories.services import ServicesRepository
from ..models.services_db import (
    ServiceAccessRightsAtDB,
    ServiceMetaDataDBPatch,
    ServiceWithHistoryDBGet,
)
from ..services import manifest
from ..services.director import DirectorApi
from .compatibility import evaluate_service_compatibility_map
from .function_services import is_function_service

_logger = logging.getLogger(__name__)


def _db_to_api_model(
    service_db: ServiceWithHistoryDBGet,
    access_rights_db: list[ServiceAccessRightsAtDB],
    service_manifest: ServiceMetaDataPublished,
    compatibility_map: dict[ServiceVersion, Compatibility | None] | None = None,
) -> ServiceGetV2:
    compatibility_map = compatibility_map or {}

    return ServiceGetV2(
        key=service_db.key,
        version=service_db.version,
        name=service_db.name,
        thumbnail=HttpUrl(service_db.thumbnail) if service_db.thumbnail else None,
        icon=HttpUrl(service_db.icon) if service_db.icon else None,
        description=service_db.description,
        description_ui=service_db.description_ui,
        version_display=service_db.version_display,
        service_type=service_manifest.service_type,
        contact=service_manifest.contact,
        authors=service_manifest.authors,
        owner=(service_db.owner_email if service_db.owner_email else None),
        inputs=service_manifest.inputs or {},
        outputs=service_manifest.outputs or {},
        boot_options=service_manifest.boot_options,
        min_visible_inputs=service_manifest.min_visible_inputs,
        access_rights={
            a.gid: ServiceGroupAccessRightsV2.model_construct(
                execute=a.execute_access,
                write=a.write_access,
            )
            for a in access_rights_db
        },
        classifiers=service_db.classifiers,
        quality=service_db.quality,
        history=[
            ServiceRelease.model_construct(
                version=h.version,
                version_display=h.version_display,
                released=h.created,
                retired=h.deprecated,
                compatibility=compatibility_map.get(h.version),
            )
            for h in service_db.history
        ],
    )


async def list_services_paginated(
    repo: ServicesRepository,
    director_api: DirectorApi,
    product_name: ProductName,
    user_id: UserID,
    limit: PageLimitInt | None,
    offset: NonNegativeInt = 0,
) -> tuple[NonNegativeInt, list[ServiceItemList]]:

    # defines the order
    total_count, services = await repo.list_latest_services(
        product_name=product_name, user_id=user_id, limit=limit, offset=offset
    )

    if services:
        # injects access-rights
        access_rights: dict[
            tuple[str, str], list[ServiceAccessRightsAtDB]
        ] = await repo.batch_get_services_access_rights(
            ((s.key, s.version) for s in services), product_name=product_name
        )
        if not access_rights:
            raise CatalogForbiddenError(
                name="any service",
                user_id=user_id,
                product_name=product_name,
            )

    # get manifest of those with access rights
    got = await manifest.get_batch_services(
        [(s.key, s.version) for s in services if access_rights.get((s.key, s.version))],
        director_api,
    )
    service_manifest = {
        (s.key, s.version): s for s in got if isinstance(s, ServiceMetaDataPublished)
    }

    items = [
        _db_to_api_model(
            service_db=sc,
            access_rights_db=ar,
            service_manifest=sm,
            compatibility_map=cm,
        )
        for sc in services
        if (
            (ar := access_rights.get((sc.key, sc.version)))
            and (sm := service_manifest.get((sc.key, sc.version)))
            and (
                # NOTE: This operation might be resource-intensive.
                # It is temporarily implemented on a trial basis.
                cm := await evaluate_service_compatibility_map(
                    repo,
                    product_name=product_name,
                    user_id=user_id,
                    service_release_history=sc.history,
                )
            )
        )
    ]

    def _get_release(item: ServiceGetV2) -> ServiceRelease:
        for rs in item.history:
            if rs.version == item.version:
                return rs
        return ServiceRelease(
            version=item.version, version_display=item.version_display, released=None
        )

    return total_count, [
        ServiceItemList.model_validate(
            {
                **it.model_dump(exclude_unset=True, by_alias=True),
                "release": _get_release(it),
            }
        )
        for it in items
    ]


async def get_service(
    repo: ServicesRepository,
    director_api: DirectorApi,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> ServiceGetV2:

    access_rights = await repo.get_service_access_rights(
        key=service_key,
        version=service_version,
        product_name=product_name,
    )
    if not access_rights:
        raise CatalogItemNotFoundError(
            name=f"{service_key}:{service_version}",
            service_key=service_key,
            service_version=service_version,
            user_id=user_id,
            product_name=product_name,
        )

    service = await repo.get_service_with_history(
        product_name=product_name,
        user_id=user_id,
        key=service_key,
        version=service_version,
    )
    if not service:
        # no service found provided `access_rights`
        raise CatalogForbiddenError(
            name=f"{service_key}:{service_version}",
            service_key=service_key,
            service_version=service_version,
            user_id=user_id,
            product_name=product_name,
        )

    service_manifest = await manifest.get_service(
        key=service_key,
        version=service_version,
        director_client=director_api,
    )

    compatibility_map = await evaluate_service_compatibility_map(
        repo,
        product_name=product_name,
        user_id=user_id,
        service_release_history=service.history,
    )

    return _db_to_api_model(service, access_rights, service_manifest, compatibility_map)


async def update_service(
    repo: ServicesRepository,
    director_api: DirectorApi,
    *,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    update: ServiceUpdateV2,
) -> ServiceGetV2:

    if is_function_service(service_key):
        raise CatalogForbiddenError(
            name=f"function service {service_key}:{service_version}",
            service_key=service_key,
            service_version=service_version,
            user_id=user_id,
            product_name=product_name,
        )

    access_rights = await repo.get_service_access_rights(
        key=service_key, version=service_version, product_name=product_name
    )

    if not access_rights:
        raise CatalogItemNotFoundError(
            name=f"{service_key}:{service_version}",
            service_key=service_key,
            service_version=service_version,
            user_id=user_id,
            product_name=product_name,
        )

    if not await repo.can_update_service(
        product_name=product_name,
        user_id=user_id,
        key=service_key,
        version=service_version,
    ):
        raise CatalogForbiddenError(
            name=f"{service_key}:{service_version}",
            service_key=service_key,
            service_version=service_version,
            user_id=user_id,
            product_name=product_name,
        )

    # Updates service_meta_data
    await repo.update_service(
        service_key,
        service_version,
        ServiceMetaDataDBPatch.model_validate(
            update.model_dump(
                exclude_unset=True, exclude={"access_rights"}, mode="json"
            ),
        ),
    )

    # Updates service_access_rights (they can be added/removed/modified)
    if update.access_rights:

        # before
        previous_gids = [r.gid for r in access_rights]

        # new
        new_access_rights = [
            ServiceAccessRightsAtDB(
                key=service_key,
                version=service_version,
                gid=gid,
                execute_access=rights.execute,
                write_access=rights.write,
                product_name=product_name,
            )
            for gid, rights in update.access_rights.items()
        ]
        await repo.upsert_service_access_rights(new_access_rights)

        # then delete the ones that were removed
        removed_access_rights = [
            ServiceAccessRightsAtDB(
                key=service_key,
                version=service_version,
                gid=gid,
                product_name=product_name,
            )
            for gid in previous_gids
            if gid not in update.access_rights
        ]
        await repo.delete_service_access_rights(removed_access_rights)

    return await get_service(
        repo=repo,
        director_api=director_api,
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
    )


async def check_for_service(
    repo: ServicesRepository,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> None:
    """Raises if the service canot be read

    Raises:
        CatalogItemNotFoundError: service (key,version) not found
        CatalogForbiddenError: insufficient access rights to get read accss
    """

    access_rights = await repo.get_service_access_rights(
        key=service_key,
        version=service_version,
        product_name=product_name,
    )
    if not access_rights:
        raise CatalogItemNotFoundError(
            name=f"{service_key}:{service_version}",
            service_key=service_key,
            service_version=service_version,
            user_id=user_id,
            product_name=product_name,
        )

    if not await repo.can_get_service(
        product_name=product_name,
        user_id=user_id,
        key=service_key,
        version=service_version,
    ):
        raise CatalogForbiddenError(
            name=f"{service_key}:{service_version}",
            service_key=service_key,
            service_version=service_version,
            user_id=user_id,
            product_name=product_name,
        )


async def batch_get_my_services(
    repo: ServicesRepository,
    groups_repo: GroupsRepository,
    *,
    product_name: ProductName,
    user_id: UserID,
    ids: list[
        tuple[
            ServiceKey,
            ServiceVersion,
        ]
    ],
) -> list[MyServiceGet]:

    services_access_rights = await repo.batch_get_services_access_rights(
        key_versions=ids, product_name=product_name
    )

    user_groups = await groups_repo.list_user_groups(user_id=user_id)
    my_group_ids = {g.gid for g in user_groups}

    my_services = []
    for service_key, service_version in ids:

        # Evaluate user's access-rights to this service key:version
        access_rights = services_access_rights.get((service_key, service_version), [])
        my_access_rights = ServiceGroupAccessRightsV2(execute=False, write=False)
        for ar in access_rights:
            if ar.gid in my_group_ids:
                my_access_rights.execute |= ar.execute_access
                my_access_rights.write |= ar.write_access

        # Get service metadata
        service_db = await repo.get_service(
            product_name=product_name,
            key=service_key,
            version=service_version,
        )
        assert service_db  # nosec

        # Find service owner
        owner: GroupID | None = service_db.owner
        if not owner:
            # NOTE can be more than one. Just get first.
            owner = next(
                ar.gid for ar in access_rights if ar.write_access and ar.execute_access
            )

        # TODO: raise error to indicate that no owner is registered for a given service
        assert owner is not None  # nosec

        # Evaluate `compatibility`
        compatibility: Compatibility | None = None
        if my_access_rights.execute or my_access_rights.write:
            # TODO: add cache to this section that evals compatibility_map based on service_key

            # NOTE: that the service history might be different for each user
            # since access rights are defined on a k:v basis
            history = await repo.get_service_history(
                product_name=product_name, user_id=user_id, key=service_key
            )
            assert history  # nosec

            compatibility_map = await evaluate_service_compatibility_map(
                repo,
                product_name=product_name,
                user_id=user_id,
                service_release_history=history,
            )
            compatibility = compatibility_map.get(service_db.version)

        my_services.append(
            MyServiceGet(
                key=service_db.key,
                release=ServiceRelease(
                    version=service_db.version,
                    version_display=service_db.version_display,
                    released=service_db.created,
                    retired=service_db.deprecated,
                    compatibility=compatibility,
                ),
                owner=owner,
                my_access_rights=my_access_rights,
            )
        )

    return my_services
