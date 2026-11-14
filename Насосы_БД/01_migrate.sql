-- PostgreSQL 14+. Additive migration; no DROP/TRUNCATE/DELETE of existing data.
BEGIN;
SET LOCAL search_path = public, pg_catalog;
SET LOCAL lock_timeout = '10s';
SELECT pg_advisory_xact_lock(102, 20261113);

CREATE TABLE IF NOT EXISTS equipment (
    id bigserial PRIMARY KEY, tag text NOT NULL UNIQUE, serial_no text,
    name text NOT NULL, location text, rated_current_a numeric, rated_efficiency numeric
);
-- The supplied INSERTs are the only available description of the old schema.
-- Refuse ambiguous identities rather than merge unrelated assets.
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM equipment GROUP BY tag HAVING count(*) > 1) THEN
   RAISE EXCEPTION 'Duplicate equipment.tag. Resolve duplicates before migration; no data was changed.';
 END IF;
END $$;
CREATE UNIQUE INDEX IF NOT EXISTS equipment_tag_uq_v2 ON equipment(tag);

CREATE TABLE IF NOT EXISTS pump_models (
    id bigserial PRIMARY KEY, model_code text NOT NULL UNIQUE,
    manufacturer text, pump_type text, description text
);
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS model_id bigint REFERENCES pump_models(id);
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS data_origin text NOT NULL DEFAULT 'unknown';
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS identity_note text;
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS commissioned_on date;

CREATE TABLE IF NOT EXISTS measurements (
    id bigserial PRIMARY KEY, equipment_id bigint NOT NULL REFERENCES equipment(id),
    measured_at timestamptz NOT NULL, vibration_mm_s numeric, vib_axial_mm_s numeric,
    temperature_c numeric, pressure_in_bar numeric, pressure_out_bar numeric,
    current_a numeric, efficiency_pct numeric, acoustic_db numeric, operating_hours numeric
);
ALTER TABLE measurements ADD COLUMN IF NOT EXISTS vib_axial_mm_s numeric;
ALTER TABLE measurements ADD COLUMN IF NOT EXISTS efficiency_pct numeric;
ALTER TABLE measurements ADD COLUMN IF NOT EXISTS acoustic_db numeric;
ALTER TABLE measurements ADD COLUMN IF NOT EXISTS operating_hours numeric;
ALTER TABLE measurements ADD COLUMN IF NOT EXISTS data_origin text NOT NULL DEFAULT 'unknown';
ALTER TABLE measurements ADD COLUMN IF NOT EXISTS sample_key text;
CREATE UNIQUE INDEX IF NOT EXISTS measurements_sample_key_uq_v2 ON measurements(sample_key);
CREATE INDEX IF NOT EXISTS measurements_equipment_time_v2 ON measurements(equipment_id, measured_at DESC);

CREATE TABLE IF NOT EXISTS documents (
    id bigserial PRIMARY KEY, sha256 text NOT NULL UNIQUE CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    filename text NOT NULL, mime_type text NOT NULL, content bytea NOT NULL,
    size_bytes bigint NOT NULL CHECK (size_bytes > 0), source_url text,
    text_status text NOT NULL CHECK (text_status IN ('text','partial','needs_ocr')),
    imported_at timestamptz NOT NULL DEFAULT now(),
    CHECK (octet_length(content) = size_bytes),
    CHECK (encode(pg_catalog.sha256(content), 'hex') = sha256)
);
CREATE TABLE IF NOT EXISTS document_pages (
    document_id bigint NOT NULL REFERENCES documents(id),
    page_no integer NOT NULL CHECK (page_no > 0), extracted_text text NOT NULL,
    extraction_method text NOT NULL,
    PRIMARY KEY(document_id, page_no)
);
CREATE TABLE IF NOT EXISTS equipment_documents (
    equipment_id bigint NOT NULL REFERENCES equipment(id),
    document_id bigint NOT NULL REFERENCES documents(id),
    role text NOT NULL, relation_basis text NOT NULL,
    PRIMARY KEY(equipment_id, document_id, role)
);
CREATE TABLE IF NOT EXISTS model_documents (
    model_id bigint NOT NULL REFERENCES pump_models(id),
    document_id bigint NOT NULL REFERENCES documents(id), role text NOT NULL,
    PRIMARY KEY(model_id, document_id, role)
);
CREATE TABLE IF NOT EXISTS equipment_passports (
    id bigserial PRIMARY KEY, equipment_id bigint NOT NULL REFERENCES equipment(id),
    document_id bigint NOT NULL REFERENCES documents(id),
    revision text NOT NULL DEFAULT 'provided', is_current boolean NOT NULL DEFAULT true,
    identity_page integer NOT NULL CHECK(identity_page > 0),
    imported_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(equipment_id, document_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS passport_one_current_v2
    ON equipment_passports(equipment_id) WHERE is_current;

-- Separate model catalogue values from values in the passport of an actual asset.
CREATE TABLE IF NOT EXISTS passport_parameters (
    id bigserial PRIMARY KEY, passport_id bigint REFERENCES equipment_passports(id),
    model_id bigint REFERENCES pump_models(id),
    code text NOT NULL, label text NOT NULL, value_num numeric, value_text text,
    min_value numeric, max_value numeric, unit text,
    operating_condition text NOT NULL DEFAULT '', source_document_id bigint NOT NULL REFERENCES documents(id),
    source_page integer CHECK(source_page > 0), source_locator text NOT NULL,
    verification_status text NOT NULL CHECK(verification_status IN ('verified_from_document','needs_review')),
    CHECK ((passport_id IS NOT NULL)::integer + (model_id IS NOT NULL)::integer = 1),
    CHECK (num_nonnulls(value_num,value_text,min_value,max_value) > 0),
    CHECK (min_value IS NULL OR max_value IS NULL OR min_value <= max_value)
);
CREATE UNIQUE INDEX IF NOT EXISTS parameter_passport_code_v2
 ON passport_parameters(passport_id,code,operating_condition) WHERE passport_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS parameter_model_code_v2
 ON passport_parameters(model_id,code,operating_condition) WHERE model_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS equipment_components (
    id bigserial PRIMARY KEY, equipment_id bigint NOT NULL REFERENCES equipment(id),
    code text NOT NULL, name text NOT NULL, model text, material text,
    source_document_id bigint REFERENCES documents(id), source_page integer CHECK(source_page > 0),
    UNIQUE(equipment_id,code)
);
-- Monitoring limits are not copied automatically from fluid temperature limits,
-- guarantee periods, test currents or generic catalogue values.
CREATE TABLE IF NOT EXISTS equipment_limits (
    id bigserial PRIMARY KEY, equipment_id bigint NOT NULL REFERENCES equipment(id),
    metric text NOT NULL, unit text NOT NULL, lower_bound numeric, upper_bound numeric,
    source_document_id bigint REFERENCES documents(id), source_locator text NOT NULL,
    status text NOT NULL CHECK(status IN ('draft','approved','demo')),
    approved_by text, approved_at timestamptz,
    CHECK(lower_bound IS NOT NULL OR upper_bound IS NOT NULL),
    CHECK(lower_bound IS NULL OR upper_bound IS NULL OR lower_bound <= upper_bound),
    CHECK(status <> 'approved' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)),
    UNIQUE(equipment_id,metric,status)
);
CREATE TABLE IF NOT EXISTS maintenance_plans (
    id bigserial PRIMARY KEY, equipment_id bigint NOT NULL REFERENCES equipment(id),
    code text NOT NULL, description text NOT NULL, interval_hours numeric CHECK(interval_hours > 0),
    source_document_id bigint REFERENCES documents(id), source_locator text NOT NULL,
    status text NOT NULL CHECK(status IN ('draft','approved','demo')),
    UNIQUE(equipment_id,code), CHECK(status <> 'approved' OR source_document_id IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS maintenance_events (
    id bigserial PRIMARY KEY, plan_id bigint NOT NULL REFERENCES maintenance_plans(id),
    performed_at timestamptz NOT NULL, operating_hours numeric CHECK(operating_hours >= 0),
    performed_by text NOT NULL, notes text
);
CREATE TABLE IF NOT EXISTS inspections (
    id bigserial PRIMARY KEY, equipment_id bigint NOT NULL REFERENCES equipment(id),
    created_at timestamptz NOT NULL DEFAULT now(), frame_id text NOT NULL,
    image_document_id bigint REFERENCES documents(id),
    observations jsonb NOT NULL DEFAULT '[]', decision text NOT NULL
      CHECK(decision IN ('pending','confirmed','rejected')), engineer text, notes text
);
CREATE TABLE IF NOT EXISTS pumps_schema_migrations (
    version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO pumps_schema_migrations(version) VALUES ('2026-11-13-passports-v2') ON CONFLICT DO NOTHING;

CREATE OR REPLACE VIEW v_equipment_passport AS
SELECT e.id AS equipment_id,e.tag,e.serial_no,e.name,e.location,e.data_origin,e.identity_note,
 m.model_code,m.manufacturer,m.pump_type,p.id AS passport_id,p.document_id AS passport_document_id,
 coalesce((SELECT jsonb_agg(jsonb_build_object(
    'code',x.code,'label',x.label,'value',x.value_num,'text',x.value_text,
    'min',x.min_value,'max',x.max_value,'unit',x.unit,'condition',x.operating_condition,
    'document_id',x.source_document_id,'page',x.source_page,'locator',x.source_locator,
    'verification_status',x.verification_status) ORDER BY x.code)
    FROM passport_parameters x WHERE x.passport_id=p.id),'[]'::jsonb) AS passport_parameters,
 coalesce((SELECT jsonb_agg(jsonb_build_object(
    'code',x.code,'label',x.label,'value',x.value_num,'text',x.value_text,
    'min',x.min_value,'max',x.max_value,'unit',x.unit,'condition',x.operating_condition,
    'document_id',x.source_document_id,'page',x.source_page,'locator',x.source_locator,
    'verification_status',x.verification_status) ORDER BY x.code)
    FROM passport_parameters x WHERE x.model_id=m.id),'[]'::jsonb) AS model_parameters
FROM equipment e LEFT JOIN pump_models m ON m.id=e.model_id
LEFT JOIN equipment_passports p ON p.equipment_id=e.id AND p.is_current;

CREATE OR REPLACE VIEW v_equipment_latest_measurement AS
SELECT e.id AS equipment_id,e.tag,to_jsonb(last_row) AS measurement
FROM equipment e LEFT JOIN LATERAL (
 SELECT m.* FROM measurements m WHERE m.equipment_id=e.id ORDER BY m.measured_at DESC,m.id DESC LIMIT 1
) last_row ON true;

CREATE OR REPLACE VIEW v_maintenance_due AS
SELECT p.id AS plan_id,e.tag,p.code,p.status,p.interval_hours,
 last_event.operating_hours AS hours_at_last_service,latest.operating_hours AS current_hours,
 CASE WHEN p.interval_hours IS NULL OR last_event.operating_hours IS NULL OR latest.operating_hours IS NULL
        OR latest.operating_hours < last_event.operating_hours THEN NULL
      ELSE greatest(0,p.interval_hours-(latest.operating_hours-last_event.operating_hours)) END AS hours_remaining,
 CASE WHEN p.interval_hours IS NULL OR last_event.operating_hours IS NULL OR latest.operating_hours IS NULL
        OR latest.operating_hours < last_event.operating_hours THEN NULL
      ELSE greatest(0,(latest.operating_hours-last_event.operating_hours)-p.interval_hours) END AS hours_overdue
FROM maintenance_plans p JOIN equipment e ON e.id=p.equipment_id
LEFT JOIN LATERAL (SELECT * FROM maintenance_events ev WHERE ev.plan_id=p.id
 ORDER BY ev.performed_at DESC,ev.id DESC LIMIT 1) last_event ON true
LEFT JOIN LATERAL (SELECT * FROM measurements m WHERE m.equipment_id=e.id
 ORDER BY m.measured_at DESC,m.id DESC LIMIT 1) latest ON true;
COMMIT;
