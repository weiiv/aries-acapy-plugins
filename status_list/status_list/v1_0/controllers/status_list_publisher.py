"""Status list publisher controller."""

from typing import Any, Dict
from datetime import datetime, timedelta, timezone
import gzip
import json
import logging
import os

from aiohttp import web
from aiohttp_apispec import docs, request_schema, response_schema, match_info_schema
from marshmallow import fields
from bitarray import bitarray
from fsspec import open

from acapy_agent.admin.decorators.auth import tenant_authentication
from acapy_agent.admin.request_context import AdminRequestContext
from acapy_agent.core.error import BaseError
from acapy_agent.messaging.models.openapi import OpenAPISchema
from acapy_agent.wallet.util import bytes_to_b64

from ..models import StatusListDefinition, StatusList, StatusListEntry
from ..jwt import jwt_sign

LOGGER = logging.getLogger(__name__)


class PublishStatusListSchema(OpenAPISchema):
    """Request schema for publish_status_list."""

    issuer_did = fields.Str(
        required=True,
        metadata={
            "description": "issuer did.",
            "example": "did:web:dev.lab.di.gov.on.ca",
        },
    )
    definition_id = fields.Str(
        required=True,
        metadata={"description": "status list definition identifier."},
    )
    publish_format = fields.Str(
        required=True,
        metadata={
            "description": "status list publish format. [w3c|ietf]",
            "example": "w3c",
        },
    )
    publish_uri = fields.Str(
        required=False,
        metadata={
            "description": "publish destination uri. [file|http|ftp|s3]://path",
            "example": "/tmp/aries/bitstring",
        },
    )


class PublishStatusListResponseSchema(OpenAPISchema):
    """Response schema for publish_status_list."""

    published = fields.Bool(required=True)
    error = fields.Str(required=False, metadata={"description": "Error text"})
    definition_id = fields.Str(
        required=True, metadata={"description": "Status list definition id."}
    )


@docs(
    tags=["status-list"],
    summary="Publish all status lists under a status list definition",
)
@request_schema(PublishStatusListSchema())
@response_schema(PublishStatusListResponseSchema(), 200, description="")
@tenant_authentication
async def publish_status_list(request: web.BaseRequest):
    """Request handler for publish_status_list."""

    body: Dict[str, Any] = await request.json()
    LOGGER.debug(f"publishing status list with: {body}")

    definition_id = body.get("definition_id", None)
    issuer_did = body.get("issuer_did", None)
    publish_format = body.get("publish_format", None)
    publish_uri = body.get("publish_uri", None)

    response = []

    try:
        context: AdminRequestContext = request["context"]
        async with context.profile.session() as session:
            definition = await StatusListDefinition.retrieve_by_id(
                session, definition_id
            )
            # get all status lists with status list definition identifier
            filter = {"definition_id": definition_id}
            results = await StatusList.query(session, filter)
            
            for status_list in results:
                filter = {"status_list_id": status_list.id}
                entries = await StatusListEntry.query(session, filter)
                sorrted = sorted(entries, key=lambda entry: entry.index)
                bits = bitarray()
                for entry in sorrted:
                    bits.append(entry.status)

                bytes = gzip.compress(bits.tobytes())
                base64 = bytes_to_b64(bytes, True)

                now = datetime.now()
                validUntil = now + timedelta(days=365)
                unix_now = int(now.timestamp())
                unix_validUntil = int(validUntil.timestamp())
                ttl = 43200

                payload = {
                    "iss": issuer_did,
                    "nbf": unix_now,
                    "jti": f"urn:uuid:{status_list.id}",
                    "sub": f"https://dev.lab.di.gov.on.ca/credentials/status/{status_list.sequence}",
                }

                if publish_format == "ietf":
                    headers = {"typ": "statuslist+jwt"}
                    payload = {
                        **payload,
                        "iat": unix_now,
                        "exp": unix_validUntil,
                        "ttl": ttl,
                        "status_list": {
                            "bits": f"{status_list.entry_size}",
                            "lst": f"{base64}",
                        },
                    }
                elif publish_format == "w3c":
                    headers = {}
                    payload = {
                        **payload,
                        "vc": {
                            "published": True,
                            "definition_id": definition_id,
                            "issuer_did": issuer_did,
                            "published_at": now.isoformat(),
                            "status_list_credential": {
                                "@context": ["https://www.w3.org/ns/credentials/v2"],
                                "id": f"https://dev.lab.di.gov.on.ca/credentials/status/{status_list.sequence}",
                                "type": [
                                    "VerifiableCredential",
                                    "BitstringStatusListCredential",
                                ],
                                "issuer": f"{issuer_did}",
                                "validFrom": now.isoformat(),
                                "validUntil": validUntil.isoformat(),
                                "credentialSubject": {
                                    "id": f"https://dev.lab.di.gov.on.ca/status/{status_list.sequence}#list",
                                    "type": "BitstringStatusList",
                                    "statusPurpose": f"{definition.status_purpose}",
                                    "encodedList": f"{base64}",
                                },
                            },
                        },
                    }

                jws = await jwt_sign(
                    context.profile,
                    headers,
                    payload,
                    did=issuer_did,
                )

                # publish status list
                if publish_uri is not None:
                    file_path = f"{publish_uri}/{status_list.sequence}-{publish_format}.jwt"
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    with open(file_path, "w") as file:
                        # json.dump(vc, file, indent=4, ensure_ascii=False)
                        file.write(jws)
                
                response.append(payload)

    except BaseError as err:
        raise web.HTTPNotFound(reason=err.roll_up) from err

    return web.json_response(response)
