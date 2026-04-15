# -*- coding: utf-8 -*-
"""Backfill incident.category descriptions (bundled data uses noupdate=1)."""

from odoo import api, SUPERUSER_ID

DESCRIPTION_BY_CODE = {
    'SEC': 'Unauthorized access, intrusion, or compromise of physical or operational security controls at the site.',
    'THEFT': 'Theft, burglary, or unlawful taking of property belonging to the client, residents, or visitors.',
    'VAND': 'Deliberate damage, graffiti, or destruction of property or common-area assets.',
    'SAFE': 'Unsafe conditions posing risk of injury (e.g. slips, trips, exposed wiring, blocked exits, unsafe works).',
    'MED': 'Medical emergency requiring first aid, ambulance, or coordination with health services.',
    'FIRE': 'Fire, smoke, heat alarm activation, or related emergency response involving Civil Defence or evacuation.',
    'DIST': 'Noise complaints, disorderly conduct, or disruption affecting residents, tenants, or site operations.',
    'TRESP': 'Unauthorized persons on site or in restricted areas after warnings or without valid access.',
    'VEH': 'Road traffic or parking incident involving a motor vehicle (collision, damage, or dispute on site).',
    'ABND_VEH': 'Vehicle left unattended in violation of site rules, blocking access, or presenting a security concern.',
    'LT_PARK': 'Vehicle parked beyond permitted duration or in prohibited parking zones requiring FM or enforcement action.',
    'EQ_HO': 'Formal handover of security or operational equipment between shifts, teams, or contractors.',
    'CCTV_HO': 'Handover or status report for CCTV monitoring, recording integrity, or control-room continuity.',
    'AUTH_VISIT': 'Official visit or inspection by police, municipality, or other government authority (document agency, purpose, outcome).',
    'WEATH': 'Storm, flooding, extreme heat, sandstorm, or other natural event impacting building or site safety.',
    'EQUIP': 'Failure or unsafe operation of building systems or security equipment requiring maintenance or vendor attendance.',
    'SUSP': 'Unconfirmed but concerning behaviour, loitering, or reconnaissance warranting observation and reporting.',
    'STMT': 'Formal written statement from a witness or involved party related to an incident or investigation.',
    'FOUND': 'Item found on site and logged for safekeeping pending owner identification and return.',
    'RETURN': 'Return of a previously found lost item to its owner with handover documentation.',
    'SHORT_LET': 'Unauthorized short-term letting, misuse of staff accommodation, or unapproved commercial activity on the property.',
    'ILL_STAFF': 'Domestic or household staff employed or housed in breach of regulations or community rules.',
    'MOVE_POL': 'Breach of community rules for moving in or moving out (timing, lifts, damage, access).',
    'SALE_POL': 'Breach of sales or leasing restrictions (e.g. unauthorized brokerage, advertising, or unit use).',
    'ANIMAL': 'Breach of pet or animal keeping rules (unauthorized species, noise, waste, or leash rules).',
    'DMG_REC': 'Damage or misuse of parks, playgrounds, or other outdoor recreation facilities.',
    'DMG_COM': 'Damage or misuse of shared corridors, lobbies, amenities, or other common spaces.',
    'DMG_SPT': 'Damage or misuse of gym, courts, or leisure amenities including equipment and booking rules.',
    'DMG_POOL': 'Damage or misuse of swimming pool, pool deck, or related safety and hygiene rules.',
    'DMG_PLNT': 'Damage to landscaping, trees, planters, or irrigation affecting community appearance or safety.',
    'GARDEN': 'Poor upkeep of assigned garden or landscape areas affecting community standards or pest risk.',
    'HOME_APP': 'Unit exterior or facade not maintained to community appearance or hygiene standards.',
    'EXT_MAJ': 'Major unauthorized exterior changes (structures, cladding, extensions) without approval.',
    'EXT_MIN': 'Minor unauthorized exterior changes (satellite dishes, awnings, fixtures) without approval.',
    'SIGNAGE': 'Unauthorized, oversized, or prohibited signage or advertising visible from common areas or exterior.',
    'TERRACE': 'Unsafe or prohibited use of terraces and balconies (BBQ, storage over rail, climbing hazard, etc.).',
    'PEST': 'Inadequate pest control, infestation, or conditions attracting vermin requiring FM or vendor action.',
    'GARAGE': 'Misuse of parking garage lanes, storage, or vehicle maintenance in prohibited areas.',
    'RETAIL': 'Breach of retail or F&B lease or license conditions affecting the development or other tenants.',
    'OTHER': 'Incident not covered by a specific category; document circumstances clearly in the report narrative.',
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Category = env['incident.category'].with_context(lang='en_US')

    for code, desc in DESCRIPTION_BY_CODE.items():
        for rec in Category.search([('code', '=', code)]):
            if not rec.description:
                rec.description = desc

    for rec in Category.search([]):
        if not rec.description and rec.name:
            rec.description = rec.name
