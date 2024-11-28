"""Status list entry controller."""

import logging
import random
import threading
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

from ..models import (
    StatusListDefinition,
    StatusList,
    StatusListEntry,
    StatusListEntrySchema,
)


LOGGER = logging.getLogger(__name__)


class MatchStatusListRequest(OpenAPISchema):
    """Match info for request with status list identifier."""

    status_list_id = fields.Str(
        required=True,
        metadata={"description": "Status list identifier."},
    )


class CreateStatusListEntryRequest(OpenAPISchema):
    """Request schema for ceating status list entry."""

    definition_id = fields.Str(
        required=True,
        metadata={
            "description": "Status list definition identifier",
        },
    )


class CreateStatusListEntryResponse(OpenAPISchema):
    """Response schema for creating status list entry."""

    status_list_id = fields.Str(
        required=False,
        metadata={
            "description": "Status list identifier",
        },
    )
    entry_index = fields.Int(
        required=False,
        metadata={"description": "Status list index"},
    )
    entry_status = fields.Int(
        required=False,
        metadata={"description": "Status list entry status"},
    )


@docs(
    tags=["status-list"],
    summary="Create a status list entry",
)
@request_schema(CreateStatusListEntryRequest())
@response_schema(CreateStatusListEntryResponse(), 200, description="")
@tenant_authentication
async def create_status_list_entry(request: web.BaseRequest):
    """Request handler for creating a status list entry."""

    try:
        context: AdminRequestContext = request["context"]

        with threading.Lock():
            async with context.profile.transaction() as txn:
                # get status list id from status list definition
                body: Dict[str, Any] = await request.json()
                definition_id = body.get("definition_id", None)
                definition = await StatusListDefinition.retrieve_by_id(
                    txn, definition_id
                )
                list_cursor = definition.list_cursor

                # get status list instance
                status_list = None
                if list_cursor is not None:
                    filter = {
                        "definition_id": definition_id,
                        "sequence": str(list_cursor),
                    }
                    status_list = await StatusList.retrieve_by_tag_filter(txn, filter)

                if (
                    status_list is None
                    or status_list.entry_cursor >= status_list.list_size
                ):
                    # update status list definition list cursor
                    if definition.list_cursor is None:
                        definition.list_cursor = 0
                    else:
                        definition.list_cursor += 1
                    await definition.save(txn, reason="Update status list definition.")

                    status_list = StatusList(
                        definition_id=definition.id,
                        sequence=str(definition.list_cursor),
                        list_size=definition.list_size,
                        entry_size=definition.status_size,
                    )
                    await status_list.save(txn, reason="Create new status list.")

                    # create randomize entry list
                    entry_list = list(
                        range(0, status_list.list_size, status_list.entry_size)
                    )
                    random.shuffle(entry_list)

                    # create status entries
                    for sequence, list_index in enumerate(entry_list):
                        entry = StatusListEntry(
                            status_list_id=status_list.id,
                            id=f"{status_list.id}-{list_index}",
                            sequence=str(sequence),
                            is_assigned=False,
                            new_with_id=True,
                        )
                        await entry.save(txn, reason="Save status list entry.")

                # get a status list entry
                filter = {
                    "status_list_id": status_list.id,
                    "sequence": str(status_list.entry_cursor),
                }

                # assign a status list entry
                entry = await StatusListEntry.retrieve_by_tag_filter(txn, filter)
                entry.is_assigned = True
                await entry.save(txn, reason="Update status list entry is_assigned.")

                # increment entry cursor
                status_list.entry_cursor += status_list.entry_size
                await status_list.save(txn, reason="Update status list entry_cursor.")

                # commmit all changes
                await txn.commit()

                result = {
                    "status_list_id": status_list.id,
                    "entry_index": entry.index,
                    "entry_status": entry.status,
                }
                LOGGER.debug(f"Created status list entry: {entry}")

    except (StorageError, BaseModelError) as err:
        raise web.HTTPBadRequest(reason=err.roll_up) from err

    return web.json_response(result)


class QueryStatusListEntryRequest(OpenAPISchema):
    """Request schema for querying status list entry."""

    entry_id = fields.Str(
        required=False,
        metadata={
            "description": "Entry identifier",
        },
    )
    sequence = fields.Str(
        required=False,
        metadata={
            "description": "Entry sequence",
            "example": "16",
        },
    )


class QueryStatusListEntryResponse(OpenAPISchema):
    """Response schema for querying status list entry."""

    results = fields.Nested(
        StatusListEntrySchema(),
        many=True,
        metadata={"description": "Status list entries."},
    )


@docs(
    tags=["status-list"],
    summary="Search status list entries by filters.",
)
@match_info_schema(MatchStatusListRequest())
@querystring_schema(QueryStatusListEntryRequest())
@response_schema(QueryStatusListEntryResponse(), 200, description="")
@tenant_authentication
async def get_status_list_entries(request: web.BaseRequest):
    """Request handler for querying status list entries."""

    status_list_id = request.match_info["status_list_id"]
    entry_id = request.query.get("entry_id")

    try:
        context: AdminRequestContext = request["context"]
        async with context.profile.session() as session:
            if entry_id:
                record = await StatusListEntry.retrieve_by_id(session, entry_id)
                results = [record.serialize()]
            else:
                tag_filter = {
                    attr: value
                    for attr in ("sequence",)
                    if (value := request.query.get(attr))
                }
                tag_filter["status_list_id"] = status_list_id
                records = await StatusListEntry.query(
                    session=session, tag_filter=tag_filter
                )
                results = [record.serialize() for record in records]
    except (StorageError, BaseModelError, StorageNotFoundError) as err:
        raise web.HTTPBadRequest(reason=err.roll_up) from err

    return web.json_response({"results": results})


class MatchStatusListEntryRequest(OpenAPISchema):
    """Match info for request with status list identifier."""

    status_list_id = fields.Str(
        required=True,
        metadata={"description": "Status list identifier."},
    )
    index = fields.Int(
        required=True,
        metadata={"description": "Status list index"},
    )


@docs(
    tags=["status-list"],
    summary="Search status list entry by identifier",
)
@match_info_schema(MatchStatusListEntryRequest())
@response_schema(StatusListEntrySchema(), 200, description="")
@tenant_authentication
async def get_status_list_entry(request: web.BaseRequest):
    """Request handler for querying status list entry by identifier."""

    status_list_id = request.match_info["status_list_id"]
    index = request.match_info["index"]
    entry_id = f"{status_list_id}-{index}"

    try:
        context: AdminRequestContext = request["context"]
        async with context.profile.session() as session:
            record = await StatusListEntry.retrieve_by_id(session, entry_id)
            result = record.serialize()

    except (StorageError, BaseModelError, StorageNotFoundError) as err:
        raise web.HTTPBadRequest(reason=err.roll_up) from err

    return web.json_response(result)


class UpdateStatusListEntryRequest(OpenAPISchema):
    """Request schema for updating status list entry."""

    status = fields.Int(
        required=False,
        default=0,
        metadata={"description": "Entry status", "example": 3},
    )


@docs(
    tags=["status-list"],
    summary="Update status list entry by identifier",
)
@match_info_schema(MatchStatusListEntryRequest())
@request_schema(UpdateStatusListEntryRequest())
@response_schema(StatusListEntrySchema(), 200, description="")
@tenant_authentication
async def update_status_list_entry(request: web.BaseRequest):
    """Request handler for update status list entry by identifier."""

    status_list_id = request.match_info["status_list_id"]
    index = request.match_info["index"]
    entry_id = f"{status_list_id}-{index}"
    body: Dict[str, Any] = await request.json()
    LOGGER.debug(f"Updating status list {status_list_id} entry {index} with: {body}")

    try:
        context: AdminRequestContext = request["context"]
        async with context.profile.session() as session:
            record = await StatusListEntry.retrieve_by_id(session, entry_id)

            for attr, value in body.items():
                setattr(record, attr, value)

            await record.save(session, reason="Update status list entry.")
            result = record.serialize()

    except (StorageError, BaseModelError, StorageNotFoundError) as err:
        raise web.HTTPBadRequest(reason=err.roll_up) from err

    return web.json_response(result)


@docs(
    tags=["status-list"],
    summary="Recycle a status list entry",
)
@match_info_schema(MatchStatusListEntryRequest())
@response_schema(CreateStatusListEntryResponse(), 200, description="")
@tenant_authentication
async def recycle_status_list_entry(request: web.BaseRequest):
    """Request handler for releasing a status list entry."""

    status_list_id = request.match_info["status_list_id"]
    index = request.match_info["index"]

    try:
        context: AdminRequestContext = request["context"]
        async with context.profile.session() as session:
            filter = {"status_list_id": status_list_id, "index": index}
            entry = await StatusListEntry.retrieve_by_tag_filter(session, filter)
            
            entry.status = 0
            entry.is_assigned = False
            await entry.save(session, reason="Update status list entry.")
            LOGGER.debug(f"Released status list entry {entry}.")

    except (StorageError, BaseModelError, StorageNotFoundError) as err:
        raise web.HTTPBadRequest(reason=err.roll_up) from err

    record = {"index": entry.index, "value": entry.value}
    LOGGER.debug(f"Recycled a status list entry: {record}")

    return web.json_response(record.serialize())
