-- TexFlow: SQLite schema (normalized). Comments without semicolons and quotes.
-- name = RU, name_ro = RO, name_en = EN (empty means fall back to RU)
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS suppliers (
    id      INTEGER PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE,
    country TEXT NOT NULL DEFAULT 'TR'
);

CREATE TABLE IF NOT EXISTS size_scales (
    id      INTEGER PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE,
    name_ro TEXT NOT NULL DEFAULT '',
    name_en TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sizes (
    id       INTEGER PRIMARY KEY,
    scale_id INTEGER NOT NULL REFERENCES size_scales(id) ON DELETE CASCADE,
    code     TEXT NOT NULL,
    sort     INTEGER NOT NULL DEFAULT 0,
    UNIQUE (scale_id, code)
);

CREATE TABLE IF NOT EXISTS color_families (
    id   INTEGER PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE,
    name_ro TEXT NOT NULL DEFAULT '',
    name_en TEXT NOT NULL DEFAULT '',
    hex     TEXT NOT NULL DEFAULT '#cccccc',
    sort    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS colors (
    id        INTEGER PRIMARY KEY,
    family_id INTEGER NOT NULL REFERENCES color_families(id),
    code      TEXT NOT NULL UNIQUE,
    name      TEXT NOT NULL,
    name_ro   TEXT NOT NULL DEFAULT '',
    name_en   TEXT NOT NULL DEFAULT '',
    hex       TEXT NOT NULL DEFAULT '#cccccc'
);

CREATE TABLE IF NOT EXISTS categories (
    id            INTEGER PRIMARY KEY,
    code          TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    name_ro       TEXT NOT NULL DEFAULT '',
    name_en       TEXT NOT NULL DEFAULT '',
    size_scale_id INTEGER REFERENCES size_scales(id),
    markup_pct    REAL NOT NULL DEFAULT 100,
    duty_pct      REAL NOT NULL DEFAULT 0,
    hs_code       TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS shipments (
    id           INTEGER PRIMARY KEY,
    code         TEXT NOT NULL UNIQUE,
    supplier_id  INTEGER REFERENCES suppliers(id),
    country      TEXT NOT NULL DEFAULT 'TR',
    currency     TEXT NOT NULL DEFAULT 'USD',
    fx_rate      REAL NOT NULL DEFAULT 1,
    arrival_date TEXT NOT NULL DEFAULT '',
    freight      REAL NOT NULL DEFAULT 0,
    customs      REAL NOT NULL DEFAULT 0,
    broker       REAL NOT NULL DEFAULT 0,
    other_costs  REAL NOT NULL DEFAULT 0,
    alloc_method TEXT NOT NULL DEFAULT 'value' CHECK (alloc_method IN ('value','qty','weight')),
    status       TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','sorted','priced','closed')),
    note         TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS bags (
    id            INTEGER PRIMARY KEY,
    shipment_id   INTEGER NOT NULL REFERENCES shipments(id) ON DELETE CASCADE,
    bag_no        TEXT NOT NULL,
    weight_kg     REAL NOT NULL DEFAULT 0,
    declared_desc TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'closed' CHECK (status IN ('closed','sorting','done')),
    UNIQUE (shipment_id, bag_no)
);

-- approximate packing list as received from supplier
CREATE TABLE IF NOT EXISTS packing_lines (
    id            INTEGER PRIMARY KEY,
    shipment_id   INTEGER NOT NULL REFERENCES shipments(id) ON DELETE CASCADE,
    bag_no        TEXT NOT NULL DEFAULT '',
    category_id   INTEGER REFERENCES categories(id),
    description   TEXT NOT NULL DEFAULT '',
    qty           INTEGER NOT NULL DEFAULT 0,
    unit_price_fx REAL NOT NULL DEFAULT 0,
    weight_kg     REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS products (
    id           INTEGER PRIMARY KEY,
    style_code   TEXT NOT NULL UNIQUE,
    name         TEXT NOT NULL,
    category_id  INTEGER NOT NULL REFERENCES categories(id),
    supplier_id  INTEGER REFERENCES suppliers(id),
    composition  TEXT NOT NULL DEFAULT '',
    description  TEXT NOT NULL DEFAULT '',
    season       TEXT NOT NULL DEFAULT '',
    gender       TEXT NOT NULL DEFAULT '',
    base_cost_fx REAL NOT NULL DEFAULT 0,
    retail_price REAL,
    price_locked INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS variants (
    id         INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    color_id   INTEGER NOT NULL REFERENCES colors(id),
    size_id    INTEGER NOT NULL REFERENCES sizes(id),
    sku        TEXT NOT NULL UNIQUE,
    ean13      TEXT NOT NULL UNIQUE,
    UNIQUE (product_id, color_id, size_id)
);

-- every counted batch of pieces taken out of a bag
CREATE TABLE IF NOT EXISTS intake_items (
    id               INTEGER PRIMARY KEY,
    shipment_id      INTEGER NOT NULL REFERENCES shipments(id) ON DELETE CASCADE,
    bag_id           INTEGER REFERENCES bags(id) ON DELETE SET NULL,
    variant_id       INTEGER NOT NULL REFERENCES variants(id),
    qty              INTEGER NOT NULL CHECK (qty <> 0),
    unit_cost_fx     REAL NOT NULL DEFAULT 0,
    landed_unit_cost REAL,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS label_jobs (
    id         INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    format     TEXT NOT NULL,
    target     TEXT NOT NULL DEFAULT '',
    labels     INTEGER NOT NULL DEFAULT 0,
    status     TEXT NOT NULL DEFAULT 'ok',
    message    TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS ix_intake_shipment ON intake_items(shipment_id);
CREATE INDEX IF NOT EXISTS ix_intake_variant ON intake_items(variant_id);
CREATE INDEX IF NOT EXISTS ix_variants_product ON variants(product_id);
CREATE INDEX IF NOT EXISTS ix_packing_shipment ON packing_lines(shipment_id);
