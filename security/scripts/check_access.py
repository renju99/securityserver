user = env['res.users'].search([('login', '=', 'jaffar@berkeleyuae.com')])
if not user:
    print('User not found')
else:
    print('User:', user.name)
    print('Manager group:', user.has_group('guardpro.group_guardpro_manager'))
    print('Supervisor group:', user.has_group('guardpro.group_guardpro_supervisor'))
    print('Sites:', user.site_ids.mapped('name'))
    guards = env['guard.profile'].with_user(user).search([('status', '=', 'active')])
    print('Active guards visible:', len(guards))
    for g in guards:
        print('  - ', g.name, ' at sites ', g.site_ids.mapped('name'))
