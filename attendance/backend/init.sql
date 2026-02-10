-- Enable PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;

-- Sites Table
CREATE TABLE IF NOT EXISTS sites (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    location VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Roles Table
CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL
);

-- Permissions Table
CREATE TABLE IF NOT EXISTS permissions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT
);

-- Role-Permissions Mapping
CREATE TABLE IF NOT EXISTS role_permissions (
    role_id INTEGER REFERENCES roles(id),
    permission_id INTEGER REFERENCES permissions(id),
    PRIMARY KEY (role_id, permission_id)
);

-- Employees Table (Updated with RBAC and Site)
CREATE TABLE IF NOT EXISTS employees (
    id SERIAL PRIMARY KEY,
    staff_id VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE,
    password_hash TEXT,
    department_name VARCHAR(100),
    role_id INTEGER REFERENCES roles(id),
    site_id INTEGER REFERENCES sites(id),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    photo_url VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Attendance Table
CREATE TABLE IF NOT EXISTS attendance (
    id SERIAL PRIMARY KEY,
    employee_id INTEGER REFERENCES employees(id),
    check_in_time TIMESTAMP,
    check_out_time TIMESTAMP,
    check_in_coords GEOGRAPHY(POINT, 4326),
    check_out_coords GEOGRAPHY(POINT, 4326),
    site_id INTEGER REFERENCES sites(id)
);

-- LiveLogs Table with Partitioning
CREATE TABLE IF NOT EXISTS live_logs (
    id SERIAL,
    employee_id INTEGER REFERENCES employees(id),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    current_coords GEOGRAPHY(POINT, 4326),
    PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

-- Default partition
CREATE TABLE IF NOT EXISTS live_logs_default PARTITION OF live_logs DEFAULT;

-- Initial Seeding
INSERT INTO roles (name) VALUES ('HR Admin'), ('Site Supervisor'), ('Payroll'), ('Employee') ON CONFLICT DO NOTHING;
INSERT INTO sites (name, location) VALUES ('Dubai South', 'Dubai'), ('Sharjah Industrial', 'Sharjah'), ('Abu Dhabi Central', 'Abu Dhabi') ON CONFLICT DO NOTHING;
INSERT INTO permissions (name) VALUES ('view_live_gps'), ('delete_user'), ('export_payroll'), ('manage_sites') ON CONFLICT DO NOTHING;
