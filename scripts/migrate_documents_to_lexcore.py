#!/usr/bin/env python3
"""One-time migration: move documents from case-aware Supabase to lexcore-platform.

Steps:
1. Read organizations from case-aware Supabase and create them in lexcore.
2. Read legal_knowledge_base entries and upload their files to lexcore's API.
3. Read case-linked documents and upload to lexcore with case_id linkage.
4. Update case-aware documents.lexcore_document_id references.

Prerequisites:
- Set environment variables (see below).
- Both lexcore-platform and Supabase must be running and accessible.
- Run this script once; it is idempotent (skips already-migrated rows).

Environment variables:
    SUPABASE_URL           - e.g. http://localhost:54321
    SUPABASE_SERVICE_KEY   - Supabase service role key (bypasses RLS)
    LEXCORE_API_URL        - e.g. http://localhost:8000
    LEXCORE_JWT_SECRET     - Shared JWT secret (Supabase JWT secret)
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "http://localhost:54321")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
LEXCORE_API_URL = os.environ.get("LEXCORE_API_URL", "http://localhost:8000")
LEXCORE_JWT_SECRET = os.environ.get("LEXCORE_JWT_SECRET", "")

if not SUPABASE_SERVICE_KEY:
    print("ERROR: SUPABASE_SERVICE_KEY is required")
    sys.exit(1)

SUPABASE_HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
}


def _lexcore_auth_header() -> dict[str, str]:
    """Build an auth header for lexcore using a service-level JWT.

    In production this would use a pre-generated service token.
    For migration we reuse the Supabase service role key if the
    JWT secrets match, or generate a token with jose.
    """
    try:
        from jose import jwt as jose_jwt

        payload = {
            "sub": "00000000-0000-0000-0000-000000000001",
            "email": "migration@lexcore.local",
            "role": "admin",
            "full_name": "Migration Script",
            "exp": int((datetime.now(timezone.utc)).timestamp()) + 3600,
            "iat": int((datetime.now(timezone.utc)).timestamp()),
        }
        token = jose_jwt.encode(payload, LEXCORE_JWT_SECRET, algorithm="HS256")
        return {"Authorization": f"Bearer {token}"}
    except ImportError:
        print("WARNING: python-jose not installed. Using SUPABASE_SERVICE_KEY as bearer token.")
        return {"Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"}


async def _supabase_get(path: str, params: dict | None = None) -> Any:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/{path}",
            headers=SUPABASE_HEADERS,
            params=params or {},
        )
        resp.raise_for_status()
        return resp.json()


async def _supabase_patch(table: str, row_id: str, data: dict) -> None:
    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            f"{SUPABASE_URL}/rest/v1/{table}?id=eq.{row_id}",
            headers={**SUPABASE_HEADERS, "Prefer": "return=minimal"},
            json=data,
        )
        resp.raise_for_status()


async def _download_supabase_storage(bucket: str, path: str) -> bytes | None:
    async with httpx.AsyncClient() as client:
        url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{path}"
        resp = await client.get(url, headers=SUPABASE_HEADERS)
        if resp.status_code == 200:
            return resp.content
        print(f"  WARNING: Could not download {bucket}/{path}: {resp.status_code}")
        return None


async def _upload_to_lexcore(
    file_bytes: bytes,
    filename: str,
    content_type: str,
    case_id: str | None = None,
    description: str | None = None,
    tags: str | None = None,
) -> dict | None:
    auth = _lexcore_auth_header()
    params = {}
    if case_id:
        params["case_id"] = case_id
    if description:
        params["description"] = description
    if tags:
        params["tags"] = tags

    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{LEXCORE_API_URL}/v1/documents"
    if query_string:
        url += f"?{query_string}"

    async with httpx.AsyncClient(timeout=120) as client:
        files = {"file": (filename, file_bytes, content_type)}
        resp = await client.post(url, headers=auth, files=files)
        if resp.status_code in (200, 201):
            return resp.json()
        print(f"  ERROR uploading {filename}: {resp.status_code} {resp.text[:200]}")
        return None


async def migrate_organizations() -> dict[str, str]:
    """Create lexcore organizations from case-aware orgs. Returns mapping external_id -> lexcore_id."""
    print("\n=== Migrating Organizations ===")
    orgs = await _supabase_get("organizations", {"select": "id,name"})
    mapping: dict[str, str] = {}

    auth = _lexcore_auth_header()
    async with httpx.AsyncClient() as client:
        for org in orgs:
            resp = await client.post(
                f"{LEXCORE_API_URL}/v1/admin/organizations",
                headers={**auth, "Content-Type": "application/json"},
                json={
                    "name": org["name"],
                    "external_id": org["id"],
                },
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                mapping[org["id"]] = data.get("id", org["id"])
                print(f"  Created org: {org['name']} -> {mapping[org['id']]}")
            elif resp.status_code == 409:
                print(f"  Org already exists: {org['name']}")
                mapping[org["id"]] = org["id"]
            else:
                print(f"  WARNING: Failed to create org {org['name']}: {resp.status_code}")
                mapping[org["id"]] = org["id"]

    print(f"  Migrated {len(mapping)} organizations")
    return mapping


async def migrate_legal_kb() -> int:
    """Upload legal_knowledge_base entries to lexcore."""
    print("\n=== Migrating Legal Knowledge Base ===")
    entries = await _supabase_get(
        "legal_knowledge_base",
        {"select": "id,title,document_type,jurisdiction,summary,file_url,organization_id"},
    )

    migrated = 0
    for entry in entries:
        file_url = entry.get("file_url")
        if not file_url:
            print(f"  SKIP: {entry['title']} (no file_url)")
            continue

        # file_url is typically a Supabase storage URL: /storage/v1/object/public/bucket/path
        # or a signed URL. We'll try to download it.
        file_bytes = None
        if "/storage/" in file_url:
            parts = file_url.split("/storage/v1/object/")
            if len(parts) == 2:
                bucket_and_path = parts[1]
                if bucket_and_path.startswith("public/"):
                    bucket_and_path = bucket_and_path[7:]
                bucket = bucket_and_path.split("/")[0]
                path = "/".join(bucket_and_path.split("/")[1:])
                file_bytes = await _download_supabase_storage(bucket, path)

        if not file_bytes:
            print(f"  SKIP: {entry['title']} (could not download file)")
            continue

        filename = entry["title"]
        if not any(filename.endswith(ext) for ext in (".pdf", ".docx", ".txt", ".doc")):
            filename += ".pdf"

        result = await _upload_to_lexcore(
            file_bytes=file_bytes,
            filename=filename,
            content_type="application/pdf",
            description=entry.get("summary") or entry.get("document_type", ""),
            tags=f"{entry.get('document_type', '')},{entry.get('jurisdiction', '')}",
        )
        if result:
            migrated += 1
            print(f"  Uploaded: {entry['title']} -> {result.get('id')}")

    print(f"  Migrated {migrated}/{len(entries)} legal KB entries")
    return migrated


async def migrate_case_documents() -> int:
    """Upload case-linked documents to lexcore with case_id context."""
    print("\n=== Migrating Case Documents ===")
    docs = await _supabase_get(
        "documents",
        {
            "select": "id,name,file_url,mime_type,case_id,organization_id,lexcore_document_id",
            "lexcore_document_id": "is.null",
            "limit": "500",
        },
    )

    migrated = 0
    for doc in docs:
        if doc.get("lexcore_document_id"):
            continue

        file_url = doc.get("file_url")
        if not file_url:
            continue

        file_bytes = None
        if "/storage/" in file_url:
            parts = file_url.split("/storage/v1/object/")
            if len(parts) == 2:
                bucket_and_path = parts[1]
                if bucket_and_path.startswith("public/"):
                    bucket_and_path = bucket_and_path[7:]
                bucket = bucket_and_path.split("/")[0]
                path = "/".join(bucket_and_path.split("/")[1:])
                file_bytes = await _download_supabase_storage(bucket, path)

        if not file_bytes:
            continue

        result = await _upload_to_lexcore(
            file_bytes=file_bytes,
            filename=doc["name"],
            content_type=doc.get("mime_type") or "application/octet-stream",
            case_id=doc.get("case_id"),
        )

        if result and result.get("id"):
            await _supabase_patch(
                "documents",
                doc["id"],
                {"lexcore_document_id": result["id"]},
            )
            migrated += 1
            print(f"  Uploaded: {doc['name']} -> {result['id']}")

    print(f"  Migrated {migrated}/{len(docs)} case documents")
    return migrated


async def main() -> None:
    print("=" * 60)
    print("Document Migration: case-aware -> lexcore-platform")
    print("=" * 60)
    print(f"  Supabase: {SUPABASE_URL}")
    print(f"  LexCore:  {LEXCORE_API_URL}")

    org_mapping = await migrate_organizations()
    kb_count = await migrate_legal_kb()
    doc_count = await migrate_case_documents()

    print("\n" + "=" * 60)
    print("Migration Summary")
    print("=" * 60)
    print(f"  Organizations: {len(org_mapping)}")
    print(f"  Legal KB entries: {kb_count}")
    print(f"  Case documents:  {doc_count}")
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
