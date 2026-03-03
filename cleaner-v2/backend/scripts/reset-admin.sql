-- Reset admin password. Run with: psql -U YOUR_USER -d YOUR_DB -f scripts/reset-admin.sql
-- Then login with: admin@example.com / admin123

-- Update if exists
UPDATE employees SET name = 'Admin', password_hash = '$2b$10$9BqE5JS5RILi0kQO6WyP3e0jF.pY9mLfsXSEzpSzjDS4jSWDffNZe', role = 'admin', active = true WHERE email = 'admin@example.com';

-- Insert if no row was updated (creates admin if missing)
INSERT INTO employees (name, email, password_hash, role)
SELECT 'Admin', 'admin@example.com', '$2b$10$9BqE5JS5RILi0kQO6WyP3e0jF.pY9mLfsXSEzpSzjDS4jSWDffNZe', 'admin'
WHERE NOT EXISTS (SELECT 1 FROM employees WHERE email = 'admin@example.com');
