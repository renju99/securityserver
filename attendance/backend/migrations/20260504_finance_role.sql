-- Finance portal role (read-heavy HR dashboard); safe to run multiple times
INSERT INTO roles (name) VALUES ('Finance')
ON CONFLICT (name) DO NOTHING;
