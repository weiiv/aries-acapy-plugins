"""Status list definition models."""

from typing import Optional

from acapy_agent.messaging.models.base_record import BaseRecord, BaseRecordSchema
from marshmallow import fields


class StatusListDefinition(BaseRecord):
    """Status list definition."""

    RECORD_TOPIC = "status-list"
    RECORD_TYPE = "status-list-definition"
    RECORD_ID_NAME = "id"
    TAG_NAMES = {"status_purpose"}

    class Meta:
        """Status List Definition Metadata."""

        schema_class = "StatusListDefinitionSchema"

    def __init__(
        self,
        *,
        id: Optional[str] = None,
        status_purpose: Optional[str] = None,
        status_size: Optional[int] = 1,
        status_message: Optional[dict] = None,
        list_size: Optional[int] = 131072,
        list_cursor: Optional[int] = None,
        **kwargs,
    ) -> None:
        """Initialize a new status list definition instance."""

        super().__init__(id, **kwargs)

        self.status_purpose = status_purpose
        self.status_size = status_size
        self.status_message = status_message
        self.list_size = list_size
        self.list_cursor = list_cursor

    @property
    def id(self) -> str:
        """Accessor for the ID associated with this status list definition."""
        return self._id

    @property
    def record_value(self) -> dict:
        """Return dict representation of the record for storage."""
        return {
            prop: getattr(self, prop)
            for prop in (
                "status_purpose",
                "status_size",
                "status_message",
                "list_size",
                "list_cursor",
            )
        }


class StatusListDefinitionSchema(BaseRecordSchema):
    """Status list definition schema."""

    class Meta:
        """Status list definition schema metadata."""

        model_class = "StatusListDefinition"

    id = fields.Str(
        required=False,
        metadata={
            "description": "Status list definition identifier",
        },
    )

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
    list_cursor = fields.Int(
        required=False,
        metadata={"description": "Status list cursor", "example": 0},
    )


class StatusList(BaseRecord):
    """Status list."""

    RECORD_TOPIC = "status-list"
    RECORD_TYPE = "status-list"
    RECORD_ID_NAME = "id"
    TAG_NAMES = {"definition_id", "sequence"}

    class Meta:
        """Status List Metadata."""

        schema_class = "StatusListSchema"

    def __init__(
        self,
        *,
        id: Optional[str] = None,
        sequence: Optional[str] = None,
        definition_id: str = None,
        list_size: int,
        entry_size: int,
        entry_cursor: Optional[int] = 0,
        **kwargs,
    ) -> None:
        """Initialize a new status list instance."""

        super().__init__(id, **kwargs)

        self.definition_id = definition_id
        self.sequence = sequence
        self.list_size = list_size
        self.entry_size = entry_size
        self.entry_cursor = entry_cursor

    @property
    def id(self) -> str:
        """Accessor for the ID associated with this status list."""
        return self._id

    @property
    def record_value(self) -> dict:
        """Return dict representation of the record for storage."""
        return {
            prop: getattr(self, prop)
            for prop in (
                "definition_id",
                "sequence",
                "list_size",
                "entry_size",
                "entry_cursor",
            )
        }


class StatusListSchema(BaseRecordSchema):
    """Status list Schema."""

    class Meta:
        """Status List Schema Metadata."""

        model_class = "StatusList"

    id = fields.Str(
        required=False,
        metadata={
            "description": "Status list identifier",
        },
    )

    definition_id = fields.Str(
        required=True,
        metadata={
            "description": "Status list definition identifier",
        },
    )
    sequence = fields.Str(
        required=True,
        metadata={
            "description": "Record sequence number",
            "example": "3",
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
    entry_size = fields.Int(
        required=False,
        default=1,
        metadata={
            "description": "Status list entry size in bits",
            "example": 1,
        },
    )
    entry_cursor = fields.Int(
        required=False,
        default=0,
        metadata={"description": "Status list entry cursor", "example": 0},
    )


class StatusListEntry(BaseRecord):
    """Status List Entry."""

    RECORD_TOPIC = "status-list"
    RECORD_TYPE = "status-list-entry"
    RECORD_ID_NAME = "id"
    TAG_NAMES = {"status_list_id", "sequence"}

    class Meta:
        """Status List Entry Metadata."""

        schema_class = "StatusListEntrySchema"

    def __init__(
        self,
        *,
        id: str,
        status_list_id: str,
        sequence: str,
        status: Optional[int] = 0,
        is_assigned: Optional[bool] = False,
        **kwargs,
    ) -> None:
        """Initialize a new status list entry instance."""

        super().__init__(id, **kwargs)

        self.status_list_id = status_list_id
        self.sequence = sequence
        self.status = status
        self.is_assigned = is_assigned

    @property
    def id(self) -> str:
        """Accessor for the ID associated with this entry."""
        return self._id

    @property
    def index(self) -> str:
        """Accessor for the index associated with this entry."""
        return self.id[self.id.rindex("-") + 1 :]

    @property
    def record_value(self) -> dict:
        """Return dict representation of the record for storage."""
        return {
            prop: getattr(self, prop)
            for prop in (
                "status_list_id",
                "sequence",
                "status",
                "is_assigned",
            )
        }


class StatusListEntrySchema(BaseRecordSchema):
    """StatusListEntry Schema."""

    class Meta:
        """Status List Entry Schema Metadata."""

        model_class = "StatusListEntry"

    id = fields.Str(
        required=True,
        metadata={
            "description": "Entry identifier",
        },
    )

    status_list_id = fields.Str(
        required=True,
        metadata={
            "description": "Status list identifier",
        },
    )
    sequence = fields.Str(
        required=True,
        metadata={
            "description": "Entry sequence",
            "example": "16",
        },
    )
    status = fields.Int(
        required=False,
        default=0,
        metadata={"description": "Entry status", "example": 3},
    )
    is_assigned = fields.Bool(
        required=False,
        default=False,
        metadata={
            "description": "Indicates if the entry is assigned",
            "example": False,
        },
    )
