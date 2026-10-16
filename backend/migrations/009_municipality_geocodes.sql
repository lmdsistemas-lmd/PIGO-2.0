BEGIN;

CREATE TABLE IF NOT EXISTS municipality_geocodes (
    ibge_code varchar(7) PRIMARY KEY,
    name varchar(150) NOT NULL,
    state_code varchar(2) NOT NULL,
    latitude numeric(10, 7) NOT NULL,
    longitude numeric(10, 7) NOT NULL,
    coordinate_type varchar(40) NOT NULL DEFAULT 'MUNICIPAL_SEAT',
    source varchar(120) NOT NULL,
    source_version varchar(80) NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_municipality_geocodes_ibge_code
        CHECK (ibge_code ~ '^[0-9]{7}$'),
    CONSTRAINT ck_municipality_geocodes_state_code
        CHECK (state_code ~ '^[A-Z]{2}$'),
    CONSTRAINT ck_municipality_geocodes_latitude
        CHECK (latitude BETWEEN -90 AND 90),
    CONSTRAINT ck_municipality_geocodes_longitude
        CHECK (longitude BETWEEN -180 AND 180)
);

CREATE INDEX IF NOT EXISTS ix_municipality_geocodes_name_state
    ON municipality_geocodes (state_code, lower(name));

CREATE TABLE IF NOT EXISTS municipality_coordinate_overrides (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ibge_code varchar(7),
    received_code varchar(100),
    city_name varchar(150),
    state_code varchar(2),
    latitude numeric(10, 7) NOT NULL,
    longitude numeric(10, 7) NOT NULL,
    reason text NOT NULL,
    active boolean NOT NULL DEFAULT true,
    created_by uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_municipality_overrides_ibge_code
        CHECK (ibge_code IS NULL OR ibge_code ~ '^[0-9]{7}$'),
    CONSTRAINT ck_municipality_overrides_state_code
        CHECK (state_code IS NULL OR state_code ~ '^[A-Z]{2}$'),
    CONSTRAINT ck_municipality_overrides_coordinates
        CHECK (
            latitude BETWEEN -90 AND 90
            AND longitude BETWEEN -180 AND 180
        ),
    CONSTRAINT ck_municipality_overrides_lookup
        CHECK (
            ibge_code IS NOT NULL
            OR received_code IS NOT NULL
            OR (city_name IS NOT NULL AND state_code IS NOT NULL)
        )
);

CREATE INDEX IF NOT EXISTS ix_municipality_overrides_ibge
    ON municipality_coordinate_overrides (ibge_code)
    WHERE active;

CREATE INDEX IF NOT EXISTS ix_municipality_overrides_received
    ON municipality_coordinate_overrides (received_code)
    WHERE active;

CREATE INDEX IF NOT EXISTS ix_municipality_overrides_name_state
    ON municipality_coordinate_overrides (state_code, lower(city_name))
    WHERE active;

ALTER TABLE IF EXISTS public."TB_CIDADE"
    ADD COLUMN IF NOT EXISTS "CID_CODIGO_MUNICIPIO" text;

COMMIT;
