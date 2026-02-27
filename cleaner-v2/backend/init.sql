-- Create Tables for Cleaner Attendance V2

-- Projects
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) UNIQUE,
    geofence_lat DOUBLE PRECISION NOT NULL,
    geofence_lng DOUBLE PRECISION NOT NULL,
    geofence_radius DOUBLE PRECISION DEFAULT 100.0,
    geofence_polygon TEXT, -- JSON string of points
    use_polygon BOOLEAN DEFAULT FALSE,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Washrooms
CREATE TABLE IF NOT EXISTS washrooms (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) UNIQUE,
    building VARCHAR(100),
    floor VARCHAR(50),
    room VARCHAR(50),
    qr_token VARCHAR(255) UNIQUE NOT NULL,
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Employees (Cleaners and Admins)
CREATE TABLE IF NOT EXISTS employees (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'cleaner', -- 'cleaner', 'admin', 'manager'
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Cleaning Schedules
CREATE TABLE IF NOT EXISTS schedules (
    id SERIAL PRIMARY KEY,
    washroom_id INTEGER REFERENCES washrooms(id) ON DELETE CASCADE,
    start_time TIME NOT NULL, -- e.g., '08:00:00'
    end_time TIME,
    interval_value NUMERIC NOT NULL DEFAULT 2.0,
    interval_unit VARCHAR(20) DEFAULT 'hours', -- 'hours', 'days', 'weeks'
    reference_date DATE,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Attendance (Actual logs)
CREATE TABLE IF NOT EXISTS attendance (
    id SERIAL PRIMARY KEY,
    employee_id INTEGER REFERENCES employees(id),
    washroom_id INTEGER REFERENCES washrooms(id),
    project_id INTEGER REFERENCES projects(id),
    schedule_id INTEGER REFERENCES schedules(id),
    check_in TIMESTAMP WITH TIME ZONE NOT NULL,
    check_out TIMESTAMP WITH TIME ZONE,
    lat_in DOUBLE PRECISION,
    lng_in DOUBLE PRECISION,
    lat_out DOUBLE PRECISION,
    lng_out DOUBLE PRECISION,
    distance_from_target DOUBLE PRECISION,
    status VARCHAR(20), -- 'on_time', 'late', 'missed', 'early'
    photo_in_url TEXT,
    photo_out_url TEXT,
    device_serial VARCHAR(255),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Checklist Items (Master list)
CREATE TABLE IF NOT EXISTS checklist_items (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(50), -- '24_hours', 'high_risk', etc.
    sequence INTEGER DEFAULT 10,
    active BOOLEAN DEFAULT TRUE
);

-- Cleaning Reports (Linked to attendance)
CREATE TABLE IF NOT EXISTS reports (
    id SERIAL PRIMARY KEY,
    attendance_id INTEGER REFERENCES attendance(id) ON DELETE CASCADE,
    employee_id INTEGER REFERENCES employees(id),
    date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'completed',
    notes TEXT
);

-- Report Lines (Individual tasks)
CREATE TABLE IF NOT EXISTS report_lines (
    id SERIAL PRIMARY KEY,
    report_id INTEGER REFERENCES reports(id) ON DELETE CASCADE,
    item_id INTEGER REFERENCES checklist_items(id),
    checked BOOLEAN DEFAULT FALSE,
    notes TEXT,
    photo_url TEXT
);

-- Indexes for performance
CREATE INDEX idx_attendance_employee ON attendance(employee_id);
CREATE INDEX idx_attendance_washroom ON attendance(washroom_id);
CREATE INDEX idx_attendance_check_in ON attendance(check_in);
CREATE INDEX idx_washrooms_qr ON washrooms(qr_token);
