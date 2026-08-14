#!/usr/bin/env python3
"""One-off: rename user-facing 'Site(s)' labels to 'Project(s)' in guardpro."""
from __future__ import annotations

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKIP_DIRS = {
    'migrations', 'docs', 'demo', 'i18n', 'scripts', '__pycache__', '.git',
}
SKIP_FILES = {
    'data/elearning/elearning_slides_security_cordons_incident_site.xml',
    'rename_sites_to_projects.py',
}
EXTENSIONS = {'.py', '.xml', '.js', '.html', '.rst', '.md'}

# Longest-first to avoid partial replacements.
REPLACEMENTS = [
    ('Assigned Sites Only', 'Assigned Projects Only'),
    ('Assigned Sites', 'Assigned Projects'),
    ('at Assigned Sites', 'at Assigned Projects'),
    ('Own Sites', 'Own Projects'),
    ('All Sites', 'All Projects'),
    ('Client Sites', 'Projects'),
    ('View Sites', 'View Projects'),
    ('Site Information', 'Project Information'),
    ('Site Info', 'Project Info'),
    ('Site Training Records', 'Project Training Records'),
    ('Site Training Record', 'Project Training Record'),
    ('Sites Covered Today', 'Projects Covered Today'),
    ('Sites Coverage Rate %', 'Projects Coverage Rate %'),
    ('Sites Coverage Rate', 'Projects Coverage Rate'),
    ('Sites Needing Coverage', 'Projects Needing Coverage'),
    ('Sites Covered', 'Projects Covered'),
    ('Total Sites', 'Total Projects'),
    ('Guards by Site', 'Guards by Project'),
    ('Site Guards Available', 'Project Guards Available'),
    ('Available Site Guards', 'Available Project Guards'),
    ('Site Guards', 'Project Guards'),
    ('Site Channel', 'Project Channel'),
    ('Site Manager Name', 'Project Manager Name'),
    ('Site Manager', 'Project Manager'),
    ('Site Phone', 'Project Phone'),
    ('Site Email', 'Project Email'),
    ('Site Name', 'Project Name'),
    ('Site Code', 'Project Code'),
    ('Site Type', 'Project Type'),
    ('Site Notes', 'Project Notes'),
    ('Site Geofences', 'Project Geofences'),
    ('Site Induction', 'Project Induction'),
    ('Site/Community', 'Project/Community'),
    ('Specific Site', 'Specific Project'),
    ('Current Site', 'Current Project'),
    ('Related Site', 'Related Project'),
    ('Unnamed Site', 'Unnamed Project'),
    ('Site Map', 'Project Map'),
    ('Site Photos', 'Project Photos'),
    ('Site Security Summary', 'Project Security Summary'),
    ('Site Security Status', 'Project Security Status'),
    ('Site-wise', 'Project-wise'),
    ('Community/Residential Sites', 'Community/Residential Projects'),
    ('Commercial Sites', 'Commercial Projects'),
    ('Site-Level Operations', 'Project-Level Operations'),
    ('Site Assignments Refreshed', 'Project Assignments Refreshed'),
    ('Site assignments have been refreshed', 'Project assignments have been refreshed'),
    ('Site Assignments', 'Project Assignments'),
    ('Assigned Sites and Zones', 'Assigned Projects and Zones'),
    ('Step 1 — Sites:', 'Step 1 — Projects:'),
    ('Sites must be selected first', 'Projects must be selected first'),
    ('Sites that this user has access to', 'Projects that this user has access to'),
    ('for their sites', 'for their projects'),
    ('community sites', 'community projects'),
    ('Create your first client site', 'Create your first project'),
    ('Client Site Location', 'Client Project Location'),
    ('Client Site with GPS', 'Client Project with GPS'),
    ('Client Site Model', 'Client Project Model'),
    ('Client Site List', 'Client Project List'),
    ('Client Site Form', 'Client Project Form'),
    ('Client Site Kanban', 'Client Project Kanban'),
    ('Client Site Search', 'Client Project Search'),
    ('Client Site Action', 'Client Project Action'),
    ('Client Site', 'Client Project'),
    ('Extend Client Site', 'Extend Client Project'),
    ('Client site', 'Client project'),
    ('client site', 'client project'),
    ('Cannot delete site(s)', 'Cannot delete project(s)'),
    ('Archive the site', 'Archive the project'),
    ('access the site', 'access the project'),
    ('Site not allowed for this API key', 'Project not allowed for this API key'),
    ('Site not found!', 'Project not found!'),
    ('Site not found', 'Project not found'),
    ('within the site geofence', 'within the project geofence'),
    ('site geofence', 'project geofence'),
    ('Site code must be unique', 'Project code must be unique'),
    ('archive the site', 'archive the project'),
    ('Site admin', 'Project admin'),
    ('Site visibility', 'Project visibility'),
    ('Site-linked', 'Project-linked'),
    ('Site scope', 'Project scope'),
    ('Site-assigned', 'Project-assigned'),
    ("string='Site'", "string='Project'"),
    ('string="Site"', 'string="Project"'),
    ('name="Sites"', 'name="Projects"'),
    ('<strong>Site:</strong>', '<strong>Project:</strong>'),
    ('<strong>Site</strong>', '<strong>Project</strong>'),
    ("'Site:'", "'Project:'"),
    ('"Site: "', '"Project: "'),
    ('>Sites<', '>Projects<'),
    ('>Site<', '>Project<'),
    ('filter string="Site"', 'filter string="Project"'),
    ('group_site" string="Site"', 'group_site" string="Project"'),
    ('group_by_site" string="Site"', 'group_by_site" string="Project"'),
    ('name="group_site" string="Site"', 'name="group_site" string="Project"'),
    ('_(\'Site\')', "_('Project')"),
    ("_('Site')", "_('Project')"),
    ('Site KPI', 'Project KPI'),
    ('Sanitizing Sites', 'Sanitizing Projects'),
    ('no assigned sites', 'no assigned projects'),
    ('assigned sites', 'assigned projects'),
    ('Select Site', 'Select Project'),
    ('Choose Site', 'Choose Project'),
    ('Filter by Site', 'Filter by Project'),
    ('Site Coverage Trends', 'Project Coverage Trends'),
    ('Site Performance Analysis', 'Project Performance Analysis'),
    ('Site Performance', 'Project Performance'),
    ('Site Coverage', 'Project Coverage'),
    ('Site Metrics', 'Project Metrics'),
    ('Sites Uncovered', 'Projects Uncovered'),
    ('Search Site Training', 'Search Project Training'),
    ('Site Training Session', 'Project Training Session'),
    ('View Site', 'View Project'),
    ('Guard Pro Site &amp; Zone Access', 'Guard Pro Project &amp; Zone Access'),
    ('Guard Pro Site & Zone Access', 'Guard Pro Project & Zone Access'),
    ('Site Selector', 'Project Selector'),
    ('No Site Access', 'No Project Access'),
    ('No Sites', 'No Projects'),
    ('search string="Sites"', 'search string="Projects"'),
    ('Site contacts', 'Project contacts'),
    ('Site Status', 'Project Status'),
    ('Site Location:', 'Project Location:'),
    ('Site Address:', 'Project Address:'),
    ('Expected Site', 'Expected Project'),
    ('Distance from Site', 'Distance from Project'),
    ('Unknown Site', 'Unknown Project'),
    ('No Site', 'No Project'),
    ('Site Audit', 'Project Audit'),
    ('Site assignments are', 'Project assignments are'),
    ('Site assignments', 'Project assignments'),
    ('<strong>Sites:</strong>', '<strong>Projects:</strong>'),
    ('Site latitude', 'Project latitude'),
    ('Site longitude', 'Project longitude'),
    ('/>Site: ', '/>Project: '),
    ('name="Sites"', 'name="Projects"'),
    ('By Site', 'By Project'),
]

# Patterns applied with regex (user-visible strings only)
REGEX_REPLACEMENTS = [
    (re.compile(r'(<th>)Site(</th>)'), r'\1Project\2'),
    (re.compile(r'(<td><strong>)Site(:</strong>)'), r'\1Project\2'),
    (re.compile(r'(<small class="text-muted d-block">)Site(</small>)'), r'\1Project\2'),
    (re.compile(r'(<h6>)Site Information(</h6>)'), r'\1Project Information\2'),
    (re.compile(r'placeholder="Site Name"'), 'placeholder="Project Name"'),
    (re.compile(r'placeholder="Site Code"'), 'placeholder="Project Code"'),
    (re.compile(r"<field name=\"name\">Sites</field>"), '<field name="name">Projects</field>'),
]


def should_process(rel_path: str) -> bool:
    if rel_path in SKIP_FILES:
        return False
    parts = rel_path.split(os.sep)
    if any(p in SKIP_DIRS for p in parts):
        return False
    if '/elearning/' in rel_path and 'incident_site' in rel_path:
        return False
    return os.path.splitext(rel_path)[1] in EXTENSIONS


def transform(content: str) -> str:
    for old, new in REPLACEMENTS:
        if old == new:
            continue
        content = content.replace(old, new)
    for pattern, repl in REGEX_REPLACEMENTS:
        content = pattern.sub(repl, content)
    return content


def main() -> None:
    changed = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for filename in filenames:
            abs_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(abs_path, ROOT)
            if not should_process(rel_path):
                continue
            with open(abs_path, encoding='utf-8') as f:
                original = f.read()
            updated = transform(original)
            if updated != original:
                with open(abs_path, 'w', encoding='utf-8') as f:
                    f.write(updated)
                changed.append(rel_path)
    print(f'Updated {len(changed)} files')
    for path in sorted(changed):
        print(f'  {path}')


if __name__ == '__main__':
    main()
