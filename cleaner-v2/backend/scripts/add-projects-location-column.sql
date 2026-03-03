-- Add location column to projects (for address text). Safe to run if column already exists.
ALTER TABLE projects ADD COLUMN IF NOT EXISTS location VARCHAR(500);
