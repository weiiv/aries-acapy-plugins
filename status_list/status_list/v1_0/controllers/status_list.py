"""Status list controller."""

import logging
import random
from typing import Any, Dict

from acapy_agent.admin.decorators.auth import tenant_authentication
from acapy_agent.admin.request_context import AdminRequestContext
from acapy_agent.messaging.models.base import BaseModelError
from acapy_agent.messaging.models.openapi import OpenAPISchema
from acapy_agent.storage.error import StorageError, StorageNotFoundError
from aiohttp import web
from aiohttp_apispec import (
    docs,
    request_schema,
    response_schema,
    match_info_schema,
    querystring_schema,
)
from marshmallow import fields

from ..models import StatusListDefinition, StatusList, StatusListSchema, StatusListEntry


LOGGER = logging.getLogger(__name__)


class CreateStatusListRequest(OpenAPISchema):
    """Request schema for ceating a new status list."""

    definition_id = fields.Str(
        required=True,
        metadata={
            "description": "Status list definition identifier",
        },
    )
    size = fields.Int(
        required=True,
        metadata={
            "description": "Number of entries in status list, minimum 131072",
            "example": 131072,
        },
    )
    default_status = fields.Int(
        required=False,
        default=0,
        metadata={"description": "Default status", "example": 0},
    )


class CreateStatusListResponse(OpenAPISchema):
    """Response schema for creating a status list."""

    status = fields.Bool(required=True)
    error = fields.Str(required=False, metadata={"description": "Error text"})
    id = fields.Str(required=True, metadata={"description": "status list identifier."})


@docs(
    tags=["status-list"],
    summary="Create a new status list",
)
@request_schema(CreateStatusListRequest())
@response_schema(StatusListSchema(), 200, description="")
@tenant_authentication
async def create_status_list(request: web.BaseRequest):
    """Request handler for creating a new status list."""

    body: Dict[str, Any] = await request.json()
    LOGGER.debug(f"Creating status list with: {body}")

    definition_id = body.get("definition_id", None)
    if definition_id is None:
        raise ValueError("definition_id is required.")

    size = body.get("size", None)
    if size is None:
        raise ValueError("size is required.")

    default_status = body.get("default_status", 0)

    try:
        context: AdminRequestContext = request["context"]
        async with context.profile.transaction() as txn:
            # create status list
            definition = await StatusListDefinition.retrieve_by_id(txn, definition_id)
            status_list = StatusList(
                definition_id=definition_id,
                list_size=size,
                entry_size=definition.status_size,
                default_status=default_status,
            )
            await status_list.save(txn, reason="Save status list.")

            # create randomize entry list
            entry_list = list(range(0, status_list.list_size, status_list.entry_size))
            random.shuffle(entry_list)

            # create status entries
            for sequence, list_index in enumerate(entry_list):
                entry = StatusListEntry(
                    status_list_id=status_list.id,
                    id=f"{status_list.id}-{list_index}",
                    sequence=str(sequence),
                    status=default_status,
                    is_assigned=False,
                    new_with_id=True,
                )
                await entry.save(txn, reason="Save status list entry.")

            # commit changes
            await txn.commit()
            LOGGER.debug(f"Created a status list with {status_list.list_size} entries.")

    except (StorageError, BaseModelError) as err:
        raise web.HTTPBadRequest(reason=err.roll_up) from err

    LOGGER.debug(f"Created status list: {status_list}")
    return web.json_response(status_list.serialize())


class QueryStatusListRequest(OpenAPISchema):
    """Request schema for querying status list."""

    id = fields.Str(
        required=False,
        metadata={"description": "Filter by status list identifier."},
    )
    definition_id = fields.Str(
        required=False,
        metadata={"description": "Filter by status list definition identifier."},
    )


class QueryStatusListResponse(OpenAPISchema):
    """Response schema for querying status list."""

    results = fields.Nested(
        StatusListSchema(),
        many=True,
        metadata={"description": "Status lists."},
    )


class MatchStatusListIdRequest(OpenAPISchema):
    """Match info for request with identifier."""

    id = fields.Str(
        required=True,
        metadata={"description": "status list identifier."},
    )


@docs(
    tags=["status-list"],
    summary="Search status lists by filters.",
)
@querystring_schema(QueryStatusListRequest())
@response_schema(QueryStatusListResponse(), 200, description="")
@tenant_authentication
async def get_status_lists(request: web.BaseRequest):
    """Request handler for querying status lists."""

    id = request.query.get("id")

    try:
        context: AdminRequestContext = request["context"]
        async with context.profile.session() as session:
            if id:
                record = await StatusList.retrieve_by_id(session, id)
                results = [record.serialize()]
            else:
                tag_filter = {
                    attr: value
                    for attr in ("definition_id",)
                    if (value := request.query.get(attr))
                }
                records = await StatusList.query(session=session, tag_filter=tag_filter)
                results = [record.serialize() for record in records]
    except (StorageError, BaseModelError, StorageNotFoundError) as err:

        raise web.HTTPBadRequest(reason=err.roll_up) from err

    return web.json_response({"results": results})


@docs(
    tags=["status-list"],
    summary="Search status list by identifier",
)
@match_info_schema(MatchStatusListIdRequest())
@response_schema(StatusListSchema(), 200, description="")
@tenant_authentication
async def get_status_list(request: web.BaseRequest):
    """Request handler for querying status list by identifier."""

    id = request.match_info["id"]

    try:
        context: AdminRequestContext = request["context"]
        async with context.profile.session() as session:
            record = await StatusList.retrieve_by_id(session, id)
            results = [record.serialize()]

    except (StorageError, BaseModelError, StorageNotFoundError) as err:
        raise web.HTTPBadRequest(reason=err.roll_up) from err

    return web.json_response({"results": results})


class UpdateStatusListRequest(OpenAPISchema):
    """Request schema for ceating status list."""

    entry_cursor = fields.Int(
        required=False,
        default=0,
        metadata={"description": "Status list entry cursor", "example": 0},
    )
    default_status = fields.Int(
        required=False,
        default=0,
        metadata={"description": "Default status", "example": 0},
    )


@docs(
    tags=["status-list"],
    summary="Update status list by identifier",
)
@match_info_schema(MatchStatusListIdRequest())
@request_schema(UpdateStatusListRequest())
@response_schema(StatusListSchema(), 200, description="")
@tenant_authentication
async def update_status_list(request: web.BaseRequest):
    """Request handler for update status list by identifier."""

    id = request.match_info["id"]
    body: Dict[str, Any] = await request.json()
    LOGGER.debug(f"Updating status list {id} with: {body}")

    try:
        context: AdminRequestContext = request["context"]
        async with context.profile.session() as session:
            record = await StatusList.retrieve_by_id(session, id)

            for attr, value in body.items():
                setattr(record, attr, value)

            await record.save(session, reason="Update status list.")
            result = record.serialize()

    except (StorageError, BaseModelError, StorageNotFoundError) as err:
        raise web.HTTPBadRequest(reason=err.roll_up) from err

    return web.json_response(result)


class DeleteStatusListResponse(OpenAPISchema):
    """Delete status list response."""

    deleted = fields.Str(required=True)
    id = fields.Str(required=False)
    error = fields.Str(required=False)


@docs(
    tags=["status-list"],
    summary="Delete a status list",
)
@match_info_schema(MatchStatusListIdRequest())
@response_schema(DeleteStatusListResponse(), 200, description="")
@tenant_authentication
async def delete_status_list(request: web.Request):
    """Request handler for deleting a status list."""

    id = request.match_info["id"]

    try:
        context: AdminRequestContext = request["context"]
        async with context.transaction() as txn:
            # delete status list entries
            filter = {"status_list_id": id}
            entries = await StatusListEntry.query(txn, filter)
            for entry in entries:
                await entry.delete_record(txn)

            # delete status list
            status_list = await StatusList.retrieve_by_id(txn, id)
            await status_list.delete_record(txn)

            # commit transaction
            await txn.commit()

            result = {"deleted": True, "id": id}

    except StorageNotFoundError as err:
        raise web.HTTPNotFound(reason=err.roll_up) from err
    except (StorageError, BaseModelError) as err:
        raise web.HTTPBadRequest(reason=err.roll_up) from err

    return web.json_response(result)
