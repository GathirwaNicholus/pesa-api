-- =============================================================================
-- Migration 001 — Initial Schema
-- =============================================================================
-- WHY two migration files instead of one big script?
-- In production you never drop and recreate the DB when you add a feature.
-- You apply incremental migration files in order. Tools like Alembic (Python)
-- or Flyway do this automatically. Here we do it manually to show the pattern.
--
-- Naming convention: NNN_description.sql
--   NNN  → monotonically increasing (001, 002, …)
--   This guarantees deterministic application order across environments.
-- =============================================================================

-- Enable pgcrypto for UUID generation (available on all modern Postgres)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =============================================================================
-- TABLE: users
-- =============================================================================
CREATE TABLE IF NOT EXISTS users (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    -- WHY UUID not SERIAL/BIGINT?
    -- UUIDs are globally unique across shards / microservices. You can generate
    -- them client-side without a DB round-trip. The trade-off is slightly larger
    -- index size, but for user-facing APIs this is almost always worth it.

    email         VARCHAR(255) NOT NULL,
    hashed_password TEXT       NOT NULL,
    full_name     VARCHAR(255),
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    -- TIMESTAMPTZ (timestamp with time zone) stores UTC internally and converts
    -- to local time on retrieval. ALWAYS prefer this over TIMESTAMP for
    -- anything that users in different timezones will see.

    CONSTRAINT users_email_unique UNIQUE (email)
    -- Named constraints are easier to drop/modify in future migrations.
);

-- Index on email because login queries will do: WHERE email = $1
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);


-- =============================================================================
-- TABLE: transactions
-- =============================================================================
CREATE TYPE transaction_type AS ENUM ('income', 'expense');
-- WHY ENUM?
-- Constrains values at the DB level — no application bug can insert 'expnese'.
-- Also more space-efficient than VARCHAR for high-cardinality repeated strings.

CREATE TABLE IF NOT EXISTS transactions (
    id            UUID             PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID             NOT NULL,
    amount        NUMERIC(12, 2)   NOT NULL CHECK (amount > 0),
    -- NUMERIC(12,2): exact decimal, 12 digits total, 2 after the decimal point.
    -- NEVER use FLOAT for money — floating-point arithmetic loses cents.
    -- CHECK (amount > 0) enforces positive amounts; type (income/expense)
    -- captures direction.

    currency      VARCHAR(3)       NOT NULL DEFAULT 'KES',
    -- ISO 4217 currency codes are 3 characters (KES, USD, EUR, GBP …)

    category      VARCHAR(100)     NOT NULL,
    description   TEXT,
    type          transaction_type NOT NULL,
    created_at    TIMESTAMPTZ      NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_transactions_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    -- ON DELETE CASCADE: when a user is deleted, all their transactions go too.
    -- This keeps referential integrity without application-level cleanup code.
);

-- Composite index: almost every query filters by user_id first,
-- then often filters or orders by created_at.
-- A composite index on (user_id, created_at) satisfies BOTH filters
-- in a single index scan — much faster than two separate indexes.
CREATE INDEX IF NOT EXISTS idx_transactions_user_date
    ON transactions (user_id, created_at DESC);

-- Index for category-based analytics queries
CREATE INDEX IF NOT EXISTS idx_transactions_user_category
    ON transactions (user_id, category);


-- =============================================================================
-- TABLE: budgets
-- =============================================================================
CREATE TYPE budget_period AS ENUM ('weekly', 'monthly');

CREATE TABLE IF NOT EXISTS budgets (
    id            UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID          NOT NULL,
    category      VARCHAR(100)  NOT NULL,
    limit_amount  NUMERIC(12,2) NOT NULL CHECK (limit_amount > 0),
    period        budget_period NOT NULL DEFAULT 'monthly',
    start_date    DATE          NOT NULL,
    -- DATE (not TIMESTAMPTZ) — budget periods are calendar-date-based,
    -- not timestamp-based. Simpler comparisons, no timezone edge cases.

    is_active     BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_budgets_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,

    -- A user should have at most one active budget per category per period.
    -- UNIQUE constraint enforces this at the DB level.
    CONSTRAINT budgets_unique_active
        UNIQUE (user_id, category, period, start_date)
);

CREATE INDEX IF NOT EXISTS idx_budgets_user ON budgets (user_id);
CREATE INDEX IF NOT EXISTS idx_budgets_user_category ON budgets (user_id, category);


-- =============================================================================
-- VIEWS — non-trivial analytical queries as reusable DB views
-- =============================================================================

-- View: monthly spend per category per user
-- WHY a view?
-- Encapsulates a complex query. The API can SELECT from this view with a simple
-- WHERE clause. If the query logic changes, you update the view once, not every
-- place in the codebase.
CREATE OR REPLACE VIEW v_monthly_spend AS
SELECT
    t.user_id,
    DATE_TRUNC('month', t.created_at)  AS month,
    -- DATE_TRUNC rounds a timestamp down to the start of the month.
    -- This groups all transactions in e.g. March 2025 together.
    t.category,
    SUM(t.amount)                      AS total_spent,
    COUNT(*)                           AS transaction_count
FROM transactions t
WHERE t.type = 'expense'
GROUP BY t.user_id, DATE_TRUNC('month', t.created_at), t.category;


-- View: budget overage alerts
-- Returns rows where a user has spent MORE than their budget limit in the
-- current period.
CREATE OR REPLACE VIEW v_budget_overages AS
SELECT
    b.id            AS budget_id,
    b.user_id,
    b.category,
    b.limit_amount,
    b.period,
    COALESCE(spent.total, 0)           AS total_spent,
    -- COALESCE: if spent.total is NULL (no transactions yet), treat as 0
    COALESCE(spent.total, 0) - b.limit_amount AS overage_amount,
    CASE
        WHEN COALESCE(spent.total, 0) >= b.limit_amount THEN TRUE
        ELSE FALSE
    END AS is_over_budget
FROM budgets b
LEFT JOIN (
    -- LEFT JOIN: include budgets even if there are no matching transactions
    SELECT
        user_id,
        category,
        SUM(amount) AS total
    FROM transactions
    WHERE
        type = 'expense'
        AND created_at >= DATE_TRUNC('month', NOW())
        -- DATE_TRUNC('month', NOW()) = first day of the current month
    GROUP BY user_id, category
) spent ON b.user_id = spent.user_id AND b.category = spent.category
WHERE b.is_active = TRUE;
