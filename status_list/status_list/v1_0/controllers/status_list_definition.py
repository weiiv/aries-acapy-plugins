"""Status list definition controller."""

import logging
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
from marshmallow.validate import OneOf

from ..models import StatusListDefinition, StatusListDefinitionSchema, StatusList


LOGGER = logging.getLogger(__name__)


class CreateStatusListDefRequest(OpenAPISchema):
    """Request schema for creating status list definition."""

    status_purpose = fields.Str(
        required=False,
        default="revocation",
        metadata={
            "description": "Status purpose: revocation, suspension or message",
            "example": "revocation",
        },
    )
    status_size = fields.Int(
        required=False,
        default=1,
        metadata={"description": "Status size in bits", "example": 1},
    )
    status_message = fields.Dict(
        required=False,
        default=None,
        metadata={
            "description": "Status List message status",
            "example": {
                "0x00": "active",
                "0x01": "revoked",
                "0x10": "pending",
                "0x11": "suspended",
            },
        },
    )
    list_size = fields.Int(
        required=False,
        default=131072,
        metadata={
            "description": "Number of entries in status list, minimum 131072",
            "example": 131072,
        },
    )


class CreateStatusListDefResponse(OpenAPISchema):
    """Response schema for creating status list definition."""

    status = fields.Bool(required=True)
    error = fields.Str(required=False, metadata={"description": "Error text"})
    id = fields.Str(
        required=True, metadata={"description": "status list definition id."}
    )


@docs(
    tags=["status-list"],
    summary="Create a new status list definition",
)
@request_schema(CreateStatusListDefRequest())
@response_schema(StatusListDefinitionSchema(), 200, description="")
@tenant_authentication
async def create_status_list_def(request: web.BaseRequest):
    """Request handler for creating a status list definition."""

    body: Dict[str, Any] = await request.json()
    LOGGER.debug(f"Creating status list definition with: {body}")

    status_purpose = body.get("status_purpose", None)
    if status_purpose is None:
        raise ValueError("status_purpose is required.")

    status_size = body.get("status_size", None)
    if status_size is None:
        raise ValueError("status_size is required.")

    if status_size > 1:
        status_message = body.get("status_message", None)
        if status_message is None:
            raise ValueError("status_message is required.")
    else:
        status_message = None

    if status_purpose == "message" and status_message is None:
        raise ValueError("status_message is required.")

    list_size = body.get("list_size", None)

    record = StatusListDefinition(
        status_purpose=status_purpose,
        status_size=status_size,
        status_message=status_message,
        list_size=list_size,
    )

    try:
        context: AdminRequestContext = request["context"]
        async with context.profile.session() as session:
            await record.save(session, reason="Save status list definition.")

    except (StorageError, BaseModelError) as err:
        raise web.HTTPBadRequest(reason=err.roll_up) from err

    LOGGER.debug(f"Created status list definition: {record}")

    return web.json_response(record.serialize())


class QueryStatusListDefRequest(OpenAPISchema):
    """Request schema for querying status list definition."""

    id = fields.Str(
        required=False,
        metadata={"description": "Filter by status list definition identitifier."},
    )
    status_purpose = fields.Str(
        required=False,
        validate=OneOf(["revocation", "suspension", "message"]),
        metadata={"description": "Filter by status purpose."},
    )


class QueryStatusListDefResponse(OpenAPISchema):
    """Response schema for querying status list definition."""

    results = fields.Nested(
        StatusListDefinitionSchema(),
        many=True,
        metadata={"description": "Status list definitions."},
    )


class MatchStatusListDefIdRequest(OpenAPISchema):
    """Match info for request with id."""

    id = fields.Str(
        required=True,
        metadata={"description": "status list definition identifier."},
    )


@docs(
    tags=["status-list"],
    summary="Search status list definitions by filters.",
)
@querystring_schema(QueryStatusListDefRequest())
@response_schema(QueryStatusListDefResponse(), 200, description="")
@tenant_authentication
async def get_status_list_defs(request: web.BaseRequest):
    """Request handler for querying status list definitions."""

    id = request.query.get("id")

    try:
        context: AdminRequestContext = request["context"]
        async with context.profile.session() as session:
            if id:
                record = await StatusListDefinition.retrieve_by_id(session, id)
                results = [record.serialize()]
            else:
                tag_filter = {
                    attr: value
                    for attr in ("status_purpose",)
                    if (value := request.query.get(attr))
                }
                records = await StatusListDefinition.query(
                    session=session, tag_filter=tag_filter
                )
                results = [record.serialize() for record in records]
    except (StorageError, BaseModelError, StorageNotFoundError) as err:
        raise web.HTTPBadRequest(reason=err.roll_up) from err

    return web.json_response({"results": results})


@docs(
    tags=["status-list"],
    summary="Search status list definition by identifier",
)
@match_info_schema(MatchStatusListDefIdRequest())
@response_schema(StatusListDefinitionSchema(), 200, description="")
@tenant_authentication
async def get_status_list_def(request: web.BaseRequest):
    """Request handler for querying status list definition by identifier."""

    id = request.match_info["id"]

    try:
        context: AdminRequestContext = request["context"]
        async with context.profile.session() as session:
            record = await StatusListDefinition.retrieve_by_id(session, id)
            results = [record.serialize()]

    except (StorageError, BaseModelError, StorageNotFoundError) as err:
        raise web.HTTPBadRequest(reason=err.roll_up) from err

    return web.json_response({"results": results})


@docs(
    tags=["status-list"],
    summary="Update status list definition by identifier",
)
@match_info_schema(MatchStatusListDefIdRequest())
@request_schema(CreateStatusListDefRequest())
@response_schema(StatusListDefinitionSchema(), 200, description="")
@tenant_authentication
async def update_status_list_def(request: web.BaseRequest):
    """Request handler for update status list definition by identifier."""

    id = request.match_info["id"]
    body: Dict[str, Any] = await request.json()
    LOGGER.debug(f"Updating status list definition {id} with: {body}")

    try:
        context: AdminRequestContext = request["context"]
        async with context.profile.session() as session:
            record = await StatusListDefinition.retrieve_by_id(session, id)

            for attr, value in body.items():
                setattr(record, attr, value)

            await record.save(session, reason="Update status list definition.")
            result = record.serialize()

    except (StorageError, BaseModelError, StorageNotFoundError) as err:
        raise web.HTTPBadRequest(reason=err.roll_up) from err

    return web.json_response(result)


class DeleteStatusListDefResponse(OpenAPISchema):
    """Delete status list definition response."""

    deleted = fields.Str(required=True)
    id = fields.Str(required=False)
    error = fields.Str(required=False)


@docs(
    tags=["status-list"],
    summary="Delete a status list definition",
)
@match_info_schema(MatchStatusListDefIdRequest())
@response_schema(DeleteStatusListDefResponse(), 200, description="")
@tenant_authentication
async def delete_status_list_def(request: web.Request):
    """Request handler for deleting a status list definition."""

    id = request.match_info["id"]

    try:
        context: AdminRequestContext = request["context"]
        async with context.session() as session:
            # check if status list definition is in use
            status_lists = await StatusList.query(session, {"definition_id": id})
            if len(status_lists) == 0:
                # delete status list definition
                record = await StatusListDefinition.retrieve_by_id(session, id)
                await record.delete_record(session)

                # create response
                result = {"deleted": True, "id": id}
            else:
                result = {
                    "deleted": False,
                    "error": "status list definition is in use and cannot be deleted",
                }
    except StorageNotFoundError as err:
        raise web.HTTPNotFound(reason=err.roll_up) from err
    except (StorageError, BaseModelError) as err:
        raise web.HTTPBadRequest(reason=err.roll_up) from err

    return web.json_response(result)
