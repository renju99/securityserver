-- Store checklist results per attendance (reports created only by managers)
CREATE TABLE IF NOT EXISTS attendance_checklist_lines (
    id SERIAL PRIMARY KEY,
    attendance_id INTEGER REFERENCES attendance(id) ON DELETE CASCADE,
    item_id INTEGER REFERENCES checklist_items(id),
    checked BOOLEAN DEFAULT FALSE,
    notes TEXT
);
