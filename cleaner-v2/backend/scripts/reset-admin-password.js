/**
 * Writes a SQL file to reset the admin password. Run with any Postgres client.
 * Usage: node scripts/reset-admin-password.js
 * Then: psql -U YOUR_USER -d YOUR_DB -f scripts/reset-admin.sql
 * Or run the SQL in pgAdmin / any client.
 * Login after: admin@example.com / admin123
 */
const path = require('path');
const fs = require('fs');
const bcrypt = require('bcryptjs');

const email = 'admin@example.com';
const newPassword = 'admin123';
const name = 'Admin';
const role = 'admin';

bcrypt.hash(newPassword, 10).then((password_hash) => {
    const sql = `-- Reset admin password. Run with: psql -U YOUR_USER -d YOUR_DB -f scripts/reset-admin.sql
-- Then login with: admin@example.com / admin123

-- Update if exists
UPDATE employees SET name = '${name.replace(/'/g, "''")}', password_hash = '${password_hash}', role = '${role}', active = true WHERE email = '${email.replace(/'/g, "''")}';

-- Insert if no row was updated (creates admin if missing)
INSERT INTO employees (name, email, password_hash, role)
SELECT '${name.replace(/'/g, "''")}', '${email.replace(/'/g, "''")}', '${password_hash}', '${role}'
WHERE NOT EXISTS (SELECT 1 FROM employees WHERE email = '${email.replace(/'/g, "''")}');
`;
    const outPath = path.resolve(__dirname, 'reset-admin.sql');
    fs.writeFileSync(outPath, sql);
    console.log('Wrote', outPath);
    console.log('Run it with your Postgres client, e.g.:');
    console.log('  psql -U YOUR_USER -d YOUR_DATABASE -f backend/scripts/reset-admin.sql');
    console.log('Then login: admin@example.com / admin123');
});
