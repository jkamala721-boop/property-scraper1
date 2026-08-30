BEGIN;

CREATE SEQUENCE building_entities_building_code_seq
    AS BIGINT
    START WITH 1
    INCREMENT BY 1
    MINVALUE 1
    NO MAXVALUE
    CACHE 1;

CREATE TABLE building_entities (
    id BIGSERIAL PRIMARY KEY,
    building_code TEXT UNIQUE NOT NULL DEFAULT (
        'BENT-' || LPAD(
            nextval('building_entities_building_code_seq')::TEXT,
            6,
            '0'
        )
    ),
    canonical_name TEXT,
    normalized_name TEXT,
    location TEXT,
    standard_location TEXT,
    address_text TEXT,
    canonical_building_id BIGINT REFERENCES buildings(id),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX building_entities_normalized_name_idx
    ON building_entities (normalized_name);

CREATE INDEX building_entities_standard_location_idx
    ON building_entities (standard_location);

CREATE INDEX building_entities_canonical_building_id_idx
    ON building_entities (canonical_building_id);

COMMIT;
