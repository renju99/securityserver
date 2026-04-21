from odoo import fields
from datetime import datetime

user = env['res.users'].search([('login', '=', 'jaffar@berkeleyuae.com')])
guards = env['guard.profile'].with_user(user).search([('status', '=', 'active')])
now_utc = fields.Datetime.now()
print("Current UTC:", now_utc)

GuardLocationHistory = env['guard.location.history'].sudo()

for guard in guards:
    last_location = GuardLocationHistory.search([
        ('guard_id', '=', guard.id),
        ('is_archived', '=', False)
    ], order='timestamp desc', limit=1)
    
    if last_location:
        delta = now_utc - last_location.timestamp
        time_since_update = int(delta.total_seconds() / 60)
        print('Guard:', guard.name, '| Last Location Ping:', last_location.timestamp, '| Delta (mins):', time_since_update)
    else:
        print('Guard:', guard.name, '| No location history found')
