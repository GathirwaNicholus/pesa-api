-- =============================================================================
-- Migration 002 — Seed Data (development / demo only)
-- =============================================================================
-- WHY a separate seed file?
-- 001_init.sql is safe to run in production — it only creates structure.
-- 002_seed.sql inserts demo data. Never run seed files in production.
-- Keeping them separate makes that boundary explicit.
--
-- The seed creates two demo users with realistic Kenyan personal finance data.
-- Passwords are BCrypt hashes of "password123" — never store plaintext.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Demo Users
-- hashed_password = bcrypt("password123", rounds=12)
-- -----------------------------------------------------------------------------
INSERT INTO users (id, email, hashed_password, full_name) VALUES
(
    'a1b2c3d4-0000-0000-0000-000000000001',
    'wanjiku@example.com',
    '$2b$12$3/jtlO21AcI4lNueITNPiOntcxkWK32kAqDccIFZEPUe.aelX46GO',
    'Wanjiku Kamau'
),
(
    'a1b2c3d4-0000-0000-0000-000000000002',
    'otieno@example.com',
    '$2b$12$3/jtlO21AcI4lNueITNPiOntcxkWK32kAqDccIFZEPUe.aelX46GO',
    'Brian Otieno'
)
ON CONFLICT (email) DO NOTHING;
-- ON CONFLICT DO NOTHING: re-running the seed won't fail if users already exist.
-- This makes the seed idempotent — safe to run multiple times.


-- -----------------------------------------------------------------------------
-- Transactions for Wanjiku (last 3 months, mixed income/expense)
-- -----------------------------------------------------------------------------
INSERT INTO transactions (user_id, amount, currency, category, description, type, created_at) VALUES

-- January income
('a1b2c3d4-0000-0000-0000-000000000001', 85000.00, 'KES', 'Salary',      'January salary',          'income',  '2025-01-31 08:00:00+03'),
('a1b2c3d4-0000-0000-0000-000000000001',  5000.00, 'KES', 'Freelance',   'Graphic design gig',      'income',  '2025-01-15 14:30:00+03'),

-- January expenses
('a1b2c3d4-0000-0000-0000-000000000001', 22000.00, 'KES', 'Rent',        'January rent',            'expense', '2025-01-03 09:00:00+03'),
('a1b2c3d4-0000-0000-0000-000000000001',  8500.00, 'KES', 'Food',        'Groceries - Naivas',      'expense', '2025-01-08 11:00:00+03'),
('a1b2c3d4-0000-0000-0000-000000000001',  3200.00, 'KES', 'Transport',   'Uber + matatu Jan',       'expense', '2025-01-20 17:00:00+03'),
('a1b2c3d4-0000-0000-0000-000000000001',  2000.00, 'KES', 'Utilities',   'KPLC token Jan',          'expense', '2025-01-05 10:00:00+03'),
('a1b2c3d4-0000-0000-0000-000000000001',  1500.00, 'KES', 'Airtime',     'Safaricom bundle',        'expense', '2025-01-10 08:00:00+03'),
('a1b2c3d4-0000-0000-0000-000000000001',  4500.00, 'KES', 'Eating Out',  'Chicken Inn + Java',      'expense', '2025-01-25 13:00:00+03'),

-- February income
('a1b2c3d4-0000-0000-0000-000000000001', 85000.00, 'KES', 'Salary',      'February salary',         'income',  '2025-02-28 08:00:00+03'),

-- February expenses
('a1b2c3d4-0000-0000-0000-000000000001', 22000.00, 'KES', 'Rent',        'February rent',           'expense', '2025-02-03 09:00:00+03'),
('a1b2c3d4-0000-0000-0000-000000000001',  9200.00, 'KES', 'Food',        'Groceries - Carrefour',   'expense', '2025-02-10 11:00:00+03'),
('a1b2c3d4-0000-0000-0000-000000000001',  3800.00, 'KES', 'Transport',   'Uber Feb',                'expense', '2025-02-18 17:00:00+03'),
('a1b2c3d4-0000-0000-0000-000000000001',  1800.00, 'KES', 'Utilities',   'KPLC token Feb',          'expense', '2025-02-04 10:00:00+03'),
('a1b2c3d4-0000-0000-0000-000000000001',  6000.00, 'KES', 'Shopping',    'Clothing - Mr. Price',    'expense', '2025-02-14 15:00:00+03'),
('a1b2c3d4-0000-0000-0000-000000000001',  3500.00, 'KES', 'Eating Out',  'Valentine dinner',        'expense', '2025-02-14 20:00:00+03'),

-- March income
('a1b2c3d4-0000-0000-0000-000000000001', 85000.00, 'KES', 'Salary',      'March salary',            'income',  '2025-03-31 08:00:00+03'),
('a1b2c3d4-0000-0000-0000-000000000001',  8000.00, 'KES', 'Freelance',   'Logo design project',     'income',  '2025-03-20 12:00:00+03'),

-- March expenses
('a1b2c3d4-0000-0000-0000-000000000001', 22000.00, 'KES', 'Rent',        'March rent',              'expense', '2025-03-03 09:00:00+03'),
('a1b2c3d4-0000-0000-0000-000000000001', 10500.00, 'KES', 'Food',        'Groceries Mar',           'expense', '2025-03-12 11:00:00+03'),
('a1b2c3d4-0000-0000-0000-000000000001',  4200.00, 'KES', 'Transport',   'Uber + parking Mar',      'expense', '2025-03-22 17:00:00+03'),
('a1b2c3d4-0000-0000-0000-000000000001',  2200.00, 'KES', 'Utilities',   'KPLC + water Mar',        'expense', '2025-03-06 10:00:00+03'),
('a1b2c3d4-0000-0000-0000-000000000001',  5500.00, 'KES', 'Eating Out',  'Team lunch + date night', 'expense', '2025-03-28 19:00:00+03')

ON CONFLICT DO NOTHING;


-- -----------------------------------------------------------------------------
-- Budgets for Wanjiku
-- -----------------------------------------------------------------------------
INSERT INTO budgets (user_id, category, limit_amount, period, start_date) VALUES
('a1b2c3d4-0000-0000-0000-000000000001', 'Food',       10000.00, 'monthly', '2025-01-01'),
('a1b2c3d4-0000-0000-0000-000000000001', 'Transport',   4000.00, 'monthly', '2025-01-01'),
('a1b2c3d4-0000-0000-0000-000000000001', 'Eating Out',  4000.00, 'monthly', '2025-01-01'),
('a1b2c3d4-0000-0000-0000-000000000001', 'Shopping',    5000.00, 'monthly', '2025-01-01'),
('a1b2c3d4-0000-0000-0000-000000000001', 'Utilities',   2500.00, 'monthly', '2025-01-01')
ON CONFLICT DO NOTHING;
