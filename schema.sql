-- =====================================================================
-- FoHow Natural Solutions — Network Database
-- Target engine: SQLite 3 (also runs on MySQL/Postgres with minor tweaks
-- noted inline). Free, file-based, no server required.
-- Comfortably handles thousands of students/distributors/clients and
-- tens of thousands of sales rows — well beyond the "1,000 users" target.
-- =====================================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- STUDENTS
-- People learning about the network who have not yet referred a sale.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS students (
    id            TEXT PRIMARY KEY,              -- e.g. 's_' + random/uuid
    name          TEXT NOT NULL,
    phone         TEXT,
    location      TEXT,
    date_joined   TEXT,                           -- ISO date 'YYYY-MM-DD'
    notes         TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------
-- DISTRIBUTORS
-- Students who have been promoted after referring a paying client.
-- Tracks PV/points and qualification tier (Qualified at >= 500 PV).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS distributors (
    id                      TEXT PRIMARY KEY,
    name                    TEXT NOT NULL,
    phone                   TEXT,
    location                TEXT,
    active_since            TEXT,                 -- ISO date
    notes                   TEXT,
    points                  INTEGER NOT NULL DEFAULT 0,
    qualified               INTEGER NOT NULL DEFAULT 0 CHECK (qualified IN (0,1)),
    qualified_date          TEXT,
    promoted_from_student_id TEXT,                -- traceability back to students table
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (promoted_from_student_id) REFERENCES students(id) ON DELETE SET NULL
);

-- ---------------------------------------------------------------------
-- CLIENTS
-- People who have purchased product, optionally referred by a distributor.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS clients (
    id             TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    phone          TEXT,
    referred_by    TEXT,                          -- FK -> distributors.id, NULL = walk-in
    purchase_date  TEXT,
    products       TEXT,
    amount         REAL NOT NULL DEFAULT 0,
    location       TEXT,
    notes          TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (referred_by) REFERENCES distributors(id) ON DELETE SET NULL
);

-- ---------------------------------------------------------------------
-- SALES  (a.k.a. commissions)
-- One row per recorded sale, linked to a distributor and (optionally) a client.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sales (
    id                TEXT PRIMARY KEY,
    distributor_id    TEXT NOT NULL,
    client_id         TEXT,
    products          TEXT,
    sale_date         TEXT,
    sale_value        REAL NOT NULL DEFAULT 0,
    commission_rate   REAL NOT NULL DEFAULT 10,     -- percent
    commission_amount REAL NOT NULL DEFAULT 0,
    notes             TEXT,
    paid              INTEGER NOT NULL DEFAULT 0 CHECK (paid IN (0,1)),
    paid_date         TEXT,
    paid_method       TEXT,                          -- M-Pesa / Cash / Bank transfer / Other
    paid_ref          TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (distributor_id) REFERENCES distributors(id) ON DELETE CASCADE,
    FOREIGN KEY (client_id)      REFERENCES clients(id)      ON DELETE SET NULL
);

-- ---------------------------------------------------------------------
-- POINTS_LOG
-- Every PV/point award to a distributor, so totals are always auditable.
-- distributors.points is a running total kept in sync by trigger below.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS points_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    distributor_id  TEXT NOT NULL,
    points          INTEGER NOT NULL CHECK (points > 0),
    reason          TEXT,
    notes           TEXT,
    log_date        TEXT NOT NULL DEFAULT (date('now')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (distributor_id) REFERENCES distributors(id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- RESOURCES
-- Training materials / guides / price lists / forms / videos.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS resources (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    type         TEXT NOT NULL DEFAULT 'other'
                 CHECK (type IN ('guide','training','price','form','video','other')),
    link         TEXT,
    description  TEXT,
    date_added   TEXT NOT NULL DEFAULT (date('now')),
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- =====================================================================
-- INDEXES  (keep lookups fast even with thousands of rows)
-- =====================================================================
CREATE INDEX IF NOT EXISTS idx_distributors_qualified   ON distributors(qualified);
CREATE INDEX IF NOT EXISTS idx_distributors_name         ON distributors(name);
CREATE INDEX IF NOT EXISTS idx_students_name             ON students(name);
CREATE INDEX IF NOT EXISTS idx_clients_referred_by        ON clients(referred_by);
CREATE INDEX IF NOT EXISTS idx_clients_name               ON clients(name);
CREATE INDEX IF NOT EXISTS idx_sales_distributor_id       ON sales(distributor_id);
CREATE INDEX IF NOT EXISTS idx_sales_client_id            ON sales(client_id);
CREATE INDEX IF NOT EXISTS idx_sales_paid                 ON sales(paid);
CREATE INDEX IF NOT EXISTS idx_sales_date                 ON sales(sale_date);
CREATE INDEX IF NOT EXISTS idx_points_log_distributor_id  ON points_log(distributor_id);

-- =====================================================================
-- TRIGGERS
-- =====================================================================

-- Keep updated_at fresh on every UPDATE
CREATE TRIGGER IF NOT EXISTS trg_students_updated_at
AFTER UPDATE ON students
BEGIN
    UPDATE students SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_distributors_updated_at
AFTER UPDATE ON distributors
BEGIN
    UPDATE distributors SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_clients_updated_at
AFTER UPDATE ON clients
BEGIN
    UPDATE clients SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_sales_updated_at
AFTER UPDATE ON sales
BEGIN
    UPDATE sales SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_resources_updated_at
AFTER UPDATE ON resources
BEGIN
    UPDATE resources SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- When a points_log row is inserted: add to the distributor's running
-- total, and auto-qualify them the moment they cross 500 PV
-- (mirrors the original app's checkAutoPromote() logic).
CREATE TRIGGER IF NOT EXISTS trg_points_log_apply
AFTER INSERT ON points_log
BEGIN
    UPDATE distributors
       SET points = points + NEW.points
     WHERE id = NEW.distributor_id;

    UPDATE distributors
       SET qualified = 1,
           qualified_date = date('now')
     WHERE id = NEW.distributor_id
       AND qualified = 0
       AND points >= 500;
END;

-- =====================================================================
-- VIEWS  (pre-built reporting queries the app / analysts can select from)
-- =====================================================================

-- Per-distributor rollup: sales count, commission earned, paid, balance
CREATE VIEW IF NOT EXISTS v_distributor_summary AS
SELECT
    d.id,
    d.name,
    d.phone,
    d.location,
    d.active_since,
    d.points,
    d.qualified,
    d.qualified_date,
    COUNT(s.id)                                          AS sales_count,
    COALESCE(SUM(s.commission_amount), 0)                AS commission_earned,
    COALESCE(SUM(CASE WHEN s.paid = 1 THEN s.commission_amount ELSE 0 END), 0) AS paid_out,
    COALESCE(SUM(CASE WHEN s.paid = 0 THEN s.commission_amount ELSE 0 END), 0) AS balance_owed
FROM distributors d
LEFT JOIN sales s ON s.distributor_id = d.id
GROUP BY d.id;

-- Clients with a resolved "referred by" name (NULL = walk-in)
CREATE VIEW IF NOT EXISTS v_clients_full AS
SELECT
    c.id, c.name, c.phone, c.purchase_date, c.products, c.amount,
    c.location, c.notes,
    d.name AS referred_by_name
FROM clients c
LEFT JOIN distributors d ON d.id = c.referred_by;

-- Sales with distributor & client names resolved (what the Commissions tab shows)
CREATE VIEW IF NOT EXISTS v_sales_full AS
SELECT
    s.id, s.sale_date, d.name AS distributor_name, c.name AS client_name,
    s.products, s.sale_value, s.commission_rate, s.commission_amount,
    s.paid, s.paid_date, s.paid_method, s.paid_ref, s.notes
FROM sales s
JOIN distributors d ON d.id = s.distributor_id
LEFT JOIN clients c ON c.id = s.client_id;

-- Overview / dashboard numbers in one row
CREATE VIEW IF NOT EXISTS v_overview_stats AS
SELECT
    (SELECT COUNT(*) FROM students)                                   AS student_count,
    (SELECT COUNT(*) FROM distributors)                                AS distributor_count,
    (SELECT COUNT(*) FROM distributors WHERE qualified = 1)            AS qualified_count,
    (SELECT COUNT(*) FROM distributors WHERE qualified = 0)            AS unqualified_count,
    (SELECT COUNT(*) FROM clients)                                     AS client_count,
    (SELECT COUNT(*) FROM sales)                                       AS sales_count,
    (SELECT COALESCE(SUM(commission_amount), 0) FROM sales)            AS commission_total,
    (SELECT COALESCE(SUM(commission_amount), 0) FROM sales WHERE paid=1) AS commission_paid,
    (SELECT COALESCE(SUM(commission_amount), 0) FROM sales WHERE paid=0) AS commission_pending;
