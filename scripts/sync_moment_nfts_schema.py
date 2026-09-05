#!/usr/bin/env python3
"""
Schema sync for sm_moment_nfts table.
Idempotently creates the table if it does not exist on the target database.

Usage:
    python3 scripts/sync_moment_nfts_schema.py [--dry-run]

Refs #17
"""
import argparse
import os
import sys

# Allow running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.environ.setdefault("DATABASE_URL", "sqlite://")  # safe default for import

from sqlalchemy import inspect, text
from app.models.moment_nft import MomentNFT


DDL = """
CREATE TABLE IF NOT EXISTS sm_moment_nfts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id        UUID NOT NULL REFERENCES sm_users(id) ON DELETE CASCADE,
    attestation_id  UUID NOT NULL UNIQUE REFERENCES sm_meetup_attestations(id) ON DELETE CASCADE,
    mint_address    VARCHAR,
    metadata_uri    VARCHAR,
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    status          VARCHAR(7) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'minted', 'failed')),
    created_at      TIMESTAMP NOT NULL DEFAULT now(),
    updated_at      TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_sm_moment_nfts_owner_id ON sm_moment_nfts(owner_id);
"""


def sync_moment_nfts_schema(engine, dry_run: bool = False) -> bool:
    """Create sm_moment_nfts table if missing. Returns True if changes were made."""
    inspector = inspect(engine)
    if "sm_moment_nfts" in inspector.get_table_names():
        print("[sync] sm_moment_nfts already exists — skipping")
        return False

    if dry_run:
        print("[dry-run] Would execute:")
        print(DDL)
        return True

    with engine.begin() as conn:
        for stmt in DDL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
    print("[sync] Created sm_moment_nfts table + index")
    return True


def main():
    parser = argparse.ArgumentParser(description="Sync sm_moment_nfts schema")
    parser.add_argument("--dry-run", action="store_true", help="Print DDL without executing")
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url or db_url == "sqlite://":
        print("ERROR: Set DATABASE_URL to your Postgres connection string", file=sys.stderr)
        sys.exit(1)

    from sqlalchemy import create_engine
    engine = create_engine(db_url)
    sync_moment_nfts_schema(engine, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
