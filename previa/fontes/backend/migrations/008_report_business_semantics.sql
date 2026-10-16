BEGIN;

ALTER TABLE report_fields
    ADD COLUMN IF NOT EXISTS semantic_metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS ix_report_fields_semantic_id
    ON report_fields ((semantic_metadata ->> 'semantic_id'));

COMMIT;
