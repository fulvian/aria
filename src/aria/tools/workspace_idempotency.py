"""
Google Workspace Idempotency Utilities

Provides idempotency key generation and deduplication for create operations
to safely retry on network failures without creating duplicate resources.

Usage:
    from aria.tools.workspace_idempotency import (
        generate_idempotency_key,
        IdempotencyStore,
        track_create_operation,
    )

    key = generate_idempotency_key("create_doc", title="My Doc", parent=folder_id)
    store.track_create_operation(key, doc_id, "pending")
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum


class OperationStatus(Enum):
    """Status of an idempotent operation."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class IdempotencyRecord:
    """Record of an idempotent operation."""

    key: str
    operation: str
    resource_id: str | None
    status: OperationStatus
    created_at: int
    updated_at: int
    expires_at: int
    input_hash: str
    result_summary: str | None = None
    error_message: str | None = None

    def is_expired(self) -> bool:
        """Check if record has expired."""
        return time.time() > self.expires_at

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "operation": self.operation,
            "resource_id": self.resource_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
            "input_hash": self.input_hash,
            "result_summary": self.result_summary,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IdempotencyRecord":
        return cls(
            key=data["key"],
            operation=data["operation"],
            resource_id=data.get("resource_id"),
            status=OperationStatus(data["status"]),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            expires_at=data["expires_at"],
            input_hash=data["input_hash"],
            result_summary=data.get("result_summary"),
            error_message=data.get("error_message"),
        )


@dataclass
class IdempotencyStore:
    """
    In-memory store for tracking idempotent operations.

    For production use, replace with persistent store (Redis, SQLite, etc.)
    with TTL support.

    TTL default: 24 hours (86400 seconds)
    """

    _records: dict[str, IdempotencyRecord] = field(default_factory=dict)
    _ttl_seconds: int = 86400

    def track_create_operation(
        self,
        key: str,
        operation: str,
        resource_id: str,
        input_params: dict,
    ) -> IdempotencyRecord:
        """
        Track a create operation with its resulting resource ID.

        Args:
            key: Idempotency key
            operation: Operation name (e.g., "create_doc")
            resource_id: ID of the created resource
            input_params: Input parameters used (for hash verification)

        Returns:
            Created idempotency record
        """
        now = int(time.time() * 1000)
        expires_at = now + (self._ttl_seconds * 1000)
        input_hash = hash_input_params(input_params)

        record = IdempotencyRecord(
            key=key,
            operation=operation,
            resource_id=resource_id,
            status=OperationStatus.PENDING,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            input_hash=input_hash,
        )

        self._records[key] = record
        return record

    def mark_completed(
        self,
        key: str,
        result_summary: str | None = None,
    ) -> bool:
        """
        Mark an operation as successfully completed.

        Args:
            key: Idempotency key
            result_summary: Optional summary of result

        Returns:
            True if found and updated, False if not found
        """
        if key in self._records:
            self._records[key].status = OperationStatus.COMPLETED
            self._records[key].updated_at = int(time.time() * 1000)
            self._records[key].result_summary = result_summary
            return True
        return False

    def mark_failed(
        self,
        key: str,
        error_message: str,
    ) -> bool:
        """
        Mark an operation as failed.

        Args:
            key: Idempotency key
            error_message: Error message describing failure

        Returns:
            True if found and updated, False if not found
        """
        if key in self._records:
            self._records[key].status = OperationStatus.FAILED
            self._records[key].updated_at = int(time.time() * 1000)
            self._records[key].error_message = error_message
            return True
        return False

    def get_record(self, key: str) -> IdempotencyRecord | None:
        """
        Get idempotency record by key.

        Args:
            key: Idempotency key

        Returns:
            Record if found and not expired, None otherwise
        """
        record = self._records.get(key)
        if record and not record.is_expired():
            return record
        return None

    def check_duplicate(
        self,
        operation: str,
        input_params: dict,
    ) -> str | None:
        """
        Check if an operation was already executed.

        Args:
            operation: Operation name
            input_params: Input parameters

        Returns:
            Existing resource ID if duplicate found, None otherwise
        """
        key = generate_idempotency_key(operation, **input_params)
        record = self.get_record(key)

        if (
            record
            and record.operation == operation
            and record.input_hash == hash_input_params(input_params)
        ):
            if record.status == OperationStatus.COMPLETED:
                return record.resource_id
            if record.status == OperationStatus.PENDING:
                return None

        return None

    def cleanup_expired(self) -> int:
        """
        Remove expired records from store.

        Returns:
            Number of records removed
        """
        now = time.time()
        expired_keys = [
            key for key, record in self._records.items() if record.expires_at < now * 1000
        ]

        for key in expired_keys:
            del self._records[key]

        return len(expired_keys)


def generate_idempotency_key(
    operation: str,
    **kwargs: str | int | float | bool | None,
) -> str:
    """
    Generate deterministic idempotency key from operation and parameters.

    Uses SHA-256 hash of operation name + sorted parameters to ensure
    same inputs always produce same key.

    Args:
        operation: Operation name (e.g., "create_doc", "create_spreadsheet")
        **kwargs: Operation parameters

    Returns:
        64-character hex idempotency key

    Example:
        key = generate_idempotency_key(
            "create_doc",
            title="My Document",
            parent="folder123"
        )
    """
    # Sort kwargs by key for deterministic ordering
    sorted_params = sorted(kwargs.items(), key=lambda x: x[0])

    # Create deterministic string
    param_str = json.dumps(
        {"operation": operation, "params": sorted_params},
        sort_keys=True,
        separators=(",", ":"),
    )

    # Generate SHA-256 hash
    hash_obj = hashlib.sha256(param_str.encode("utf-8"))
    return hash_obj.hexdigest()


def hash_input_params(params: dict) -> str:
    """
    Create hash of input parameters for verification.

    Args:
        params: Input parameters dictionary

    Returns:
        64-character hex hash
    """
    # Sort keys for deterministic ordering
    sorted_params = sorted(params.items(), key=lambda x: str(x[0]))
    param_str = json.dumps(sorted_params, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(param_str.encode("utf-8")).hexdigest()


def create_idempotent_key_for_doc(
    title: str,
    parent: str | None = None,
    content: str | None = None,
) -> str:
    """
    Generate idempotency key specifically for document creation.

    Args:
        title: Document title
        parent: Optional parent folder ID
        content: Optional initial content

    Returns:
        Idempotency key
    """
    params = {"title": title}
    if parent:
        params["parent"] = parent
    if content:
        # Only use first 100 chars of content for key (avoid huge keys)
        params["content_preview"] = content[:100]

    return generate_idempotency_key("create_doc", **params)


def create_idempotent_key_for_sheet(
    title: str,
    parent: str | None = None,
    sheets: list[str] | None = None,
) -> str:
    """
    Generate idempotency key specifically for spreadsheet creation.

    Args:
        title: Spreadsheet title
        parent: Optional parent folder ID
        sheets: Optional list of sheet names

    Returns:
        Idempotency key
    """
    params = {"title": title}
    if parent:
        params["parent"] = parent
    if sheets:
        params["sheets"] = ",".join(sorted(sheets))

    return generate_idempotency_key("create_spreadsheet", **params)


def create_idempotent_key_for_slide(
    title: str,
    parent: str | None = None,
) -> str:
    """
    Generate idempotency key specifically for presentation creation.

    Args:
        title: Presentation title
        parent: Optional parent folder ID

    Returns:
        Idempotency key
    """
    params = {"title": title}
    if parent:
        params["parent"] = parent

    return generate_idempotency_key("create_presentation", **params)
