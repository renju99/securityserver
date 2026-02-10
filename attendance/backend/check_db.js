const { Pool } = require('pg');
const pool = new Pool({ connectionString: 'postgres://user:password@db:5432/attendance' });
pool.query('SELECT staff_id, photo_url, department_name FROM employees WHERE photo_url IS NOT NULL', (err, res) => {
    if (err) console.error(err);
    else console.log(JSON.stringify(res.rows, null, 2));
    pool.end();
});
