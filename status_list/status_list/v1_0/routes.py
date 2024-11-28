"""status list admin routes."""

import logging

from acapy_agent.admin.decorators.auth import tenant_authentication
from acapy_agent.messaging.models.openapi import OpenAPISchema
from acapy_agent.messaging.valid import (
    GENERIC_DID_EXAMPLE,
    GENERIC_DID_VALIDATE,
    Uri,
)
from aiohttp import web
from aiohttp_apispec import docs, request_schema, response_schema
from marshmallow import fields

from .controllers import (
    # status list definitions
    create_status_list_def,
    get_status_list_defs,
    get_status_list_def,
    update_status_list_def,
    delete_status_list_def,
    # status list
    create_status_list,
    get_status_lists,
    get_status_list,
    update_status_list,
    delete_status_list,
    # status list entries
    create_status_list_entry,
    get_status_list_entries,
    get_status_list_entry,
    update_status_list_entry,
    recycle_status_list_entry,
    # status list publisher
    publish_status_list,
)

LOGGER = logging.getLogger(__name__)


class StatusListRequestSchema(OpenAPISchema):
    """Generic request schema for status list methods."""


class StatusListResponseSchema(OpenAPISchema):
    """Generic response schema for status list methods."""


@docs(
    tags=["status-list"],
    summary="generic statis list method",
)
@request_schema(StatusListRequestSchema())
@response_schema(StatusListResponseSchema(), 200, description="")
@tenant_authentication
async def status_list_generic_method(request: web.BaseRequest):
    """Request handler for generic method."""

    result = {"status": True}
    return web.json_response(result)


async def register(app: web.Application):
    """Register routes."""
    app.add_routes(
        [
            #
            # status list definitions
            #
            web.post("/status-list/definitions", create_status_list_def),
            web.get(
                "/status-list/definitions",
                get_status_list_defs,
                allow_head=False,
            ),
            web.get(
                "/status-list/definitions/{id}",
                get_status_list_def,
                allow_head=False,
            ),
            web.patch(
                "/status-list/definitions/{id}",
                update_status_list_def,
            ),
            web.delete(
                "/status-list/definitions/{id}",
                delete_status_list_def,
            ),
            #
            # status list
            #
            # web.post("/status-lists", create_status_list),
            web.get(
                "/status-lists",
                get_status_lists,
                allow_head=False,
            ),
            web.get(
                "/status-lists/{id}",
                get_status_list,
                allow_head=False,
            ),
            web.patch("/status-lists/{id}", update_status_list),
            web.delete("/status-lists/{id}", delete_status_list),
            #
            # status list entries
            #
            web.post("/status-list/entries", create_status_list_entry),
            web.post("/status-list/{status_list_id}/entries", create_status_list_entry),
            web.get(
                "/status-list/{status_list_id}/entries",
                get_status_list_entries,
                allow_head=False,
            ),
            web.get(
                "/status-list/{status_list_id}/entries/{index}",
                get_status_list_entry,
                allow_head=False,
            ),
            web.patch(
                "/status-list/{status_list_id}/entries/{index}",
                update_status_list_entry,
            ),
            web.delete(
                "/status-list/{status_list_id}/entries/{index}",
                recycle_status_list_entry,
            ),
            #
            # status list publish
            #
            web.put("/status-list/publisher", publish_status_list),
        ]
    )


def post_process_routes(app: web.Application):
    """Amend swagger API."""

    # Add top-level tags description
    if "tags" not in app._state["swagger_dict"]:
        app._state["swagger_dict"]["tags"] = []
    app._state["swagger_dict"]["tags"].append(
        {
            "name": "status-list",
            "description": "status list management",
            "externalDocs": {
                "description": "Specification",
                "url": (
                    "[https://www.w3.org/TR/vc-bitstring-status-list/]",
                    "[https://datatracker.ietf.org/doc/draft-ietf-oauth-status-list/]",
                ),
            },
        }
    )
