# -*- coding: utf-8 -*-
"""Create/update Peninsula 3 guards only (idempotent)."""
import json
import re

DATA_PATH = "/mnt/extra-addons/guardpro/scripts/peninsula3_import_data.json"
with open(DATA_PATH, "r", encoding="utf-8") as fh:
    DATA = json.load(fh)

site = env["client.site"].search([("code", "=", "Peninsula 3")], limit=1)
assert site, "Peninsula 3 project missing"
portal_group = env.ref("guardpro.group_guardpro_guard_portal")
# Note: do NOT mix portal + internal supervisor groups (Odoo user-type conflict).
# Sheet "Supervisor" role is stored on the profile notes; portal access only.

Users = env["res.users"]
Guard = env["guard.profile"]


def _normalize_phone(mobile):
    digits = re.sub(r"\D", "", mobile or "")
    if not digits:
        return False
    if digits.startswith("971"):
        return "+" + digits
    if digits.startswith("0"):
        return "+971" + digits[1:]
    if len(digits) == 9:
        return "+971" + digits
    return mobile


created_u = existing_u = created_g = existing_g = 0
for umeta in DATA["users"]:
    email = umeta["email"].strip().lower()
    phone = _normalize_phone(umeta.get("mobile"))
    user = Users.search([("login", "=", email)], limit=1)
    if not user:
        user = Users.with_context(
            no_reset_password=True,
            mail_notrack=True,
            mail_create_nolog=True,
            mail_create_nosubscribe=True,
        ).create(
            {
                "name": umeta["name"],
                "login": email,
                "email": email,
                "share": True,
                "active": True,
                "groups_id": [(6, 0, [portal_group.id])],
                "site_ids": [(6, 0, [site.id])],
            }
        )
        if phone:
            user.partner_id.write({"phone": phone, "mobile": phone})
        created_u += 1
        print("USER created", email)
    else:
        writes = {}
        if portal_group not in user.groups_id:
            # existing internal users: only add site, don't force portal
            if user.has_group("base.group_user"):
                print("USER internal keep", email)
            else:
                writes.setdefault("groups_id", [])
                writes["groups_id"].append((4, portal_group.id))
        if site.id not in user.site_ids.ids:
            writes["site_ids"] = [(4, site.id)]
        if writes:
            user.write(writes)
        if phone and not (user.partner_id.phone or user.partner_id.mobile):
            user.partner_id.write({"phone": phone, "mobile": phone})
        existing_u += 1
        print("USER existing", email)

    guard = Guard.search([("user_id", "=", user.id)], limit=1) or Guard.search(
        [("name", "=ilike", umeta["name"])], limit=1
    )
    vals = {
        "name": umeta["name"],
        "user_id": user.id,
        "phone": phone or False,
        "status": "active",
        "availability": "full_time",
        "current_site_id": site.id,
    }
    if "notes" in Guard._fields:
        vals["notes"] = "%s shift — %s" % (umeta.get("shift") or "", umeta.get("role") or "")
    if not guard:
        guard = Guard.with_context(
            mail_notrack=True,
            mail_create_nolog=True,
            mail_create_nosubscribe=True,
        ).create(vals)
        created_g += 1
        print("GUARD created", guard.name, guard.badge_number)
    else:
        guard.with_context(mail_notrack=True).write(
            {
                "name": umeta["name"],
                "user_id": user.id,
                "phone": phone or guard.phone,
                "status": "active",
                "availability": "full_time",
                "current_site_id": site.id,
            }
        )
        existing_g += 1
        print("GUARD existing", guard.name, guard.badge_number)
    env.cr.commit()

print(
    "DONE users created/existing=%s/%s guards created/existing=%s/%s"
    % (created_u, existing_u, created_g, existing_g)
)
print(
    "Users on Peninsula 3:",
    Users.search_count([("site_ids", "in", [site.id])]),
)
