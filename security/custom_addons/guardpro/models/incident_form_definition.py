# -*- coding: utf-8 -*-
"""Excel-aligned incident form definitions.

Structure mirrors Incident Report Formats and Fields.xlsx:
  Parent Category → Form Section → Field / Subcategory Label
  with Field Type and Popup Options / Drop-down Choices.
"""
import json
import logging
import os

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

FIELD_TYPES = [
    ('char', 'Text Box'),
    ('text', 'Multiline Text'),
    ('integer', 'Number'),
    ('date', 'Date'),
    ('time', 'Time'),
    ('selection', 'Drop-down'),
    ('boolean', 'Toggle / Checkbox'),
    ('media', 'Media Attachment'),
    ('signature', 'Digital Signature'),
]


class IncidentFormParent(models.Model):
    _name = 'incident.form.parent'
    _description = 'Incident Form Parent Category'
    _order = 'sequence, name'

    name = fields.Char(required=True, index=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text()
    category_id = fields.Many2one(
        'incident.category',
        string='Linked Category',
        help='incident.category used when creating reports of this parent type.',
    )
    section_ids = fields.One2many(
        'incident.form.section', 'parent_id', string='Form Sections',
    )
    section_count = fields.Integer(compute='_compute_counts')
    field_count = fields.Integer(compute='_compute_counts')

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Form parent code must be unique.'),
    ]

    @api.depends('section_ids', 'section_ids.field_ids')
    def _compute_counts(self):
        for rec in self:
            rec.section_count = len(rec.section_ids)
            rec.field_count = sum(len(s.field_ids) for s in rec.section_ids)

    def action_open_sections(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Form Sections',
            'res_model': 'incident.form.section',
            'view_mode': 'list,form',
            'domain': [('parent_id', '=', self.id)],
            'context': {'default_parent_id': self.id},
        }

    @api.model
    def seed_from_excel_json(self, json_path=None):
        """Upsert parent/section/field definitions from the Excel-derived JSON."""
        if not json_path:
            json_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'data', 'incident_form_definitions.json',
            )
        if not os.path.isfile(json_path):
            _logger.warning('Incident form JSON not found: %s', json_path)
            return False

        with open(json_path, 'r', encoding='utf-8') as fh:
            rows = json.load(fh)

        Category = self.env['incident.category'].sudo()
        Section = self.env['incident.form.section'].sudo()
        Field = self.env['incident.form.field'].sudo()

        created_parents = 0
        for row in rows:
            code = (row.get('code') or '').strip()
            name = (row.get('name') or '').strip()
            if not code or not name:
                continue

            category = Category.search([('code', '=', code)], limit=1)
            if not category:
                # Prefer existing alias codes for known parents
                aliases = {
                    'COMM_VIO': ['VAND'],
                    'PARK_VIO': ['ILLEGAL_PARK', 'LT_PARK'],
                    'PROP_DMG': ['SAFE'],
                    'GEN_SEC': ['SEC'],
                    'ACS_REL': ['TRESP'],
                }
                for alias in aliases.get(code, []):
                    category = Category.search([('code', '=', alias)], limit=1)
                    if category:
                        break
            if not category:
                category = Category.create({
                    'name': name,
                    'code': code,
                    'sequence': row.get('sequence') or 10,
                    'description': 'Excel parent category: %s' % name,
                })

            parent = self.sudo().search([('code', '=', code)], limit=1)
            vals = {
                'name': name,
                'code': code,
                'sequence': row.get('sequence') or 10,
                'category_id': category.id,
                'active': True,
            }
            if parent:
                parent.write(vals)
            else:
                parent = self.sudo().create(vals)
                created_parents += 1

            # Replace sections/fields to stay in sync with Excel
            parent.section_ids.unlink()
            for sec in row.get('sections') or []:
                section = Section.create({
                    'parent_id': parent.id,
                    'name': sec.get('name') or 'Details',
                    'sequence': sec.get('sequence') or 10,
                })
                for fld in sec.get('fields') or []:
                    Field.create({
                        'section_id': section.id,
                        'name': fld.get('name') or 'Field',
                        'field_type': fld.get('field_type') or 'char',
                        'selection_options': fld.get('selection_options') or False,
                        'sequence': fld.get('sequence') or 10,
                        'required': bool(fld.get('required')),
                    })

        _logger.info(
            'Seeded incident form definitions: %s parents (%s new)',
            len(rows), created_parents,
        )
        return True


class IncidentFormSection(models.Model):
    _name = 'incident.form.section'
    _description = 'Incident Form Section'
    _order = 'sequence, id'

    parent_id = fields.Many2one(
        'incident.form.parent', required=True, ondelete='cascade', index=True,
    )
    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    field_ids = fields.One2many('incident.form.field', 'section_id', string='Fields')


class IncidentFormField(models.Model):
    _name = 'incident.form.field'
    _description = 'Incident Form Field'
    _order = 'sequence, id'

    section_id = fields.Many2one(
        'incident.form.section', required=True, ondelete='cascade', index=True,
    )
    parent_id = fields.Many2one(
        related='section_id.parent_id', store=True, index=True,
    )
    name = fields.Char(string='Field / Subcategory Label', required=True)
    field_type = fields.Selection(FIELD_TYPES, required=True, default='char')
    selection_options = fields.Text(
        string='Popup Options / Drop-down Choices',
        help='One option per line for drop-down fields.',
    )
    odoo_field = fields.Char(
        string='Mapped Odoo Field',
        help='Optional incident.report field name when a dedicated column exists.',
    )
    required = fields.Boolean(default=False)
    sequence = fields.Integer(default=10)

    def get_selection_list(self):
        """Drop-down choices only (Excel popup options for selection fields)."""
        self.ensure_one()
        if self.field_type != 'selection' or not self.selection_options:
            return []
        raw = self.selection_options.strip()
        parts = raw.splitlines() if '\n' in raw else raw.split(',')
        return [p.strip() for p in parts if p.strip()]

    def get_field_hint(self):
        """Excel options column used as prompt/guidance for non-dropdown fields."""
        self.ensure_one()
        if self.field_type == 'selection' or not self.selection_options:
            return ''
        return ' '.join(self.selection_options.split())


class IncidentFormValue(models.Model):
    _name = 'incident.form.value'
    _description = 'Incident Form Field Value'
    _order = 'id'

    incident_id = fields.Many2one(
        'incident.report', required=True, ondelete='cascade', index=True,
    )
    field_id = fields.Many2one(
        'incident.form.field', required=True, ondelete='cascade', index=True,
    )
    field_name = fields.Char(related='field_id.name', store=True)
    field_type = fields.Selection(related='field_id.field_type', store=True)
    value_char = fields.Char()
    value_text = fields.Text()
    value_integer = fields.Integer()
    value_boolean = fields.Boolean()
    value_date = fields.Date()
    value_time = fields.Char()
    value_binary = fields.Binary(attachment=True)
    value_filename = fields.Char()

    def get_display_value(self):
        self.ensure_one()
        t = self.field_type
        if t == 'time':
            return self.value_time or self.value_char or ''
        if t in ('char', 'selection'):
            return self.value_char or ''
        if t == 'text':
            return self.value_text or ''
        if t == 'integer':
            return str(self.value_integer) if self.value_integer is not False else ''
        if t == 'boolean':
            return 'Yes' if self.value_boolean else 'No'
        if t == 'date':
            return str(self.value_date) if self.value_date else ''
        if t in ('media', 'signature'):
            return self.value_filename or ('Attached' if self.value_binary else '')
        return self.value_char or self.value_text or ''
