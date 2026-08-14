# -*- coding: utf-8 -*-
"""Seed parking violation incident categories if missing."""

import logging

_logger = logging.getLogger(__name__)

PARKING_CATEGORIES = [
    ('DBL_PARK', 'Double Parking', 93,
     'Vehicle parked alongside another parked vehicle, obstructing the lane or flow of traffic.'),
    ('BLK_ACCESS', 'Blocking Access', 94,
     'Vehicle blocking a driveway, gate, ramp, fire lane, emergency exit, or other access point.'),
    ('ILLEGAL_PARK', 'Illegal Parking', 95,
     'Vehicle parked in a prohibited area or in breach of site parking regulations.'),
    ('VIS_PARK', 'Visitor Parking Misuse', 96,
     'Visitor bay used incorrectly (e.g. by residents, staff, or beyond allowed duration).'),
    ('WRONG_PARK', 'Wrongful Parking', 97,
     'Vehicle parked incorrectly within a bay, across lines, or otherwise wrongfully positioned.'),
    ('UNDESIG_PARK', 'Undesignated Parking', 98,
     'Vehicle parked in an area not designated for parking.'),
    ('UNAUTH_VEH', 'Unauthorized Vehicle', 99,
     'Vehicle on site without valid authorization, sticker, or visitor registration.'),
    ('PAVEMENT_PARK', 'Parking on Pavement', 100,
     'Motor vehicle parked on pavement / sidewalk.'),
    ('DISABLED_PARK', 'Disabled Parking Violation', 101,
     'Vehicle parked in a disabled / accessible bay without entitlement.'),
    ('FIRE_HYD_PARK', 'Parking in Front of Fire Hydrant', 102,
     'Vehicle parked in front of a fire hydrant or fire service point.'),
    ('LOAD_ZONE', 'Loading/Unloading Zone Violation', 103,
     'Not complying with loading and unloading in designated areas.'),
    ('PED_CROSS', 'Stopping on Pedestrian Crossing', 104,
     'Vehicle stopped on a pedestrian crossing without justified reason.'),
    ('OVERNIGHT_PARK', 'Overnight Parking', 105,
     'Vehicle left overnight in a restricted or retail parking area.'),
    ('RETAIL_PARK', 'Retail Parking Violation', 106,
     'Retail parking rule breach (e.g. tailgating, unpaid exit, lost ticket).'),
    ('NO_PAY_EXIT', 'Exit Without Payment', 107,
     'Vehicle exited paid parking without completing payment.'),
    ('LOST_TICKET', 'Lost Parking Ticket', 108,
     'Driver reports a lost parking ticket requiring verification and settlement.'),
]


def migrate(cr, version):
    env = None
    try:
        from odoo import api, SUPERUSER_ID
        env = api.Environment(cr, SUPERUSER_ID, {})
    except Exception:
        _logger.exception('Could not build environment for parking category seed')
        return

    Category = env['incident.category'].sudo()
    created = 0
    for code, name, sequence, description in PARKING_CATEGORIES:
        existing = Category.search([('code', '=', code)], limit=1)
        if existing:
            continue
        Category.create({
            'name': name,
            'code': code,
            'sequence': sequence,
            'color': 7,
            'description': description,
            'hide_from_guard_incidents': False,
        })
        created += 1
    if created:
        _logger.info('Created %s parking violation incident categories', created)
    else:
        _logger.info('Parking violation categories already present; nothing to create')
