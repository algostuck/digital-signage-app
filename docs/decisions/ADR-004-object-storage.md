# ADR-004: Media storage — S3-compatible object storage, DB holds metadata only

Status: Accepted · Date: 2026-08-29

## Context
Media binaries (video especially) must never live in PostgreSQL (SRS §11).
Delivery must be CDN-ready and access-controlled (NFR-004); uploads must be
resumable and processed asynchronously (M06).

## Decision
S3-compatible object storage behind a thin `storage` integration module
(boto3-compatible client, provider-neutral: AWS S3, MinIO for dev, or any
compatible endpoint). Key scheme:
`tenant/<org_id>/content/<asset_id>/<version>/{original|optimized|thumbnail}`.
Uploads use server-created upload sessions issuing presigned PUT/multipart
URLs; completion triggers the async processing pipeline (validate -> scan hook
-> metadata -> transcode profile -> thumbnail -> READY). Reads use short-lived
signed GET URLs (CDN-compatible). MinIO ships in docker-compose for local dev.

## Consequences
- Cloud-provider-neutral; local dev needs no AWS account.
- DB stays small and fast; storage lifecycle/versioning policies handled at
  the bucket level.
- Signed-URL issuance becomes a hot path for players — cacheable per asset
  version within the URL TTL.
