import json
from datetime import datetime
from odoo import fields

user = env['res.users'].search([('login', '=', 'jaffar@berkeleyuae.com')])
guards = env['guard.profile'].with_user(user).search([('status', '=', 'active')])

GuardLocationHistory = env['guard.location.history'].sudo()

locations = []
try:
    now_utc = fields.Datetime.now()
    for guard in guards:
        last_location = GuardLocationHistory.search([
            ('guard_id', '=', guard.id),
            ('is_archived', '=', False)
        ], order='timestamp desc', limit=1)
        
        if last_location:
            delta = now_utc - last_location.timestamp
            time_since_update = int(delta.total_seconds() / 60)
            
            if time_since_update <= 30:
                locations.append({
                    'id': guard.id,
                    'name': guard.name,
                    'latitude': float(last_location.latitude),
                    'longitude': float(last_location.longitude),
                    'time_since_update': time_since_update,
                    'badge_number': guard.badge_number,
                    'phone': guard.phone,
                    'current_site': last_location.site_id.name if last_location.site_id else guard.current_site_id.name if guard.current_site_id else 'Unassigned',
                    'current_site_id': last_location.site_id.id if last_location.site_id else guard.current_site_id.id if guard.current_site_id else None,
                })

    print("Success: locations computed:", len(locations))
    print(json.dumps(locations[:2], indent=2))
except Exception as e:
    import traceback
    print("Caught Error:", str(e))
    traceback.print_exc()
