BEGIN;

CREATE TABLE apartment_building_entities (
    id BIGSERIAL PRIMARY KEY,
    apartment_id BIGINT NOT NULL REFERENCES apartments(id),
    building_entity_id BIGINT NOT NULL REFERENCES building_entities(id),
    match_status TEXT NOT NULL DEFAULT 'candidate',
    match_confidence DOUBLE PRECISION,
    match_method TEXT,
    evidence JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT apartment_building_entities_apartment_entity_key
        UNIQUE (apartment_id, building_entity_id),
    CONSTRAINT apartment_building_entities_match_confidence_check
        CHECK (
            match_confidence IS NULL
            OR (match_confidence >= 0.0 AND match_confidence <= 1.0)
        )
);

CREATE INDEX apartment_building_entities_building_entity_id_idx
    ON apartment_building_entities (building_entity_id);

CREATE INDEX apartment_building_entities_match_status_idx
    ON apartment_building_entities (match_status);

COMMIT;
