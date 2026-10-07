# -*- coding: utf-8 -*-
"""
Idempotent Peninsula 3 import from peninsula3_import_data.json.

Usage (inside Odoo container):
  odoo shell -d security --no-http < /mnt/extra-addons/guardpro/scripts/import_peninsula3.py

Creates/updates:
  - client.site Peninsula 3
  - site.building + building.floor (52 floors)
  - 716 floor.area spaces (linked to floors)
  - 716 QR checkpoints (linked to floor + area)
  - 5 security.tour routes with ordered checkpoint lines
  - 11 portal guards assigned to the project
"""
import json
import logging
import re

_logger = logging.getLogger("peninsula3_import")

DATA_PATH = "/mnt/extra-addons/guardpro/scripts/peninsula3_import_data.json"

with open(DATA_PATH, "r", encoding="utf-8") as fh:
    DATA = json.load(fh)

Site = env["client.site"]
Building = env["site.building"]
Floor = env["building.floor"]
Area = env["floor.area"]
Checkpoint = env["checkpoint"]
Tour = env["security.tour"]
TourLine = env["security.tour.checkpoint.line"]
Guard = env["guard.profile"]
Users = env["res.users"]
Partner = env["res.partner"]

stats = {
    "floors_created": 0,
    "floors_existing": 0,
    "areas_created": 0,
    "areas_updated": 0,
    "checkpoints_created": 0,
    "checkpoints_updated": 0,
    "tours_created": 0,
    "tours_updated": 0,
    "guards_created": 0,
    "guards_existing": 0,
    "errors": [],
}


def _area_type_from_code(code):
    """Best-effort area_type from Peninsula space code token (e.g. P3-B1-STR-01)."""
    parts = (code or "").upper().split("-")
    token = parts[2] if len(parts) >= 3 else ""
    mapping = {
        "STR": "stairwell",
        "ELV": "elevator",
        "LFT": "elevator",
        "COR": "corridor",
        "LOB": "lobby",
        "RCV": "lobby",
        "WR": "restroom",
        "TOI": "restroom",
        "STRG": "storage",
        "STO": "storage",
        "PKG": "parking_area",
        "PRK": "parking_area",
        "UTL": "utility",
        "FPR": "utility",
        "GSM": "utility",
        "AHU": "utility",
        "ELEC": "utility",
        "MEP": "utility",
        "SRV": "server_room",
        "OFF": "office",
        "MTG": "meeting_room",
        "BRK": "break_room",
    }
    return mapping.get(token, "other")


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


# ---------------------------------------------------------------------------
# 1) Site
# ---------------------------------------------------------------------------
site_vals = DATA["site"]
site = Site.search([("code", "=", site_vals["code"])], limit=1) or Site.search(
    [("name", "=", site_vals["name"])], limit=1
)
if not site:
    raise Exception("Peninsula 3 site not found — expected existing project id/code.")

site_write = {
    "name": site_vals["name"],
    "code": site_vals["code"],
    "status": "active",
}
# Only set GPS if currently empty/zero
lat = float(site.latitude or 0)
lon = float(site.longitude or 0)
if abs(lat) < 0.0001 and abs(lon) < 0.0001:
    site_write["latitude"] = site_vals["latitude"]
    site_write["longitude"] = site_vals["longitude"]
site.write(site_write)
_logger.info("Site ready: %s (id=%s)", site.name, site.id)
print("SITE", site.id, site.name, site.code)

# ---------------------------------------------------------------------------
# 2) Building
# ---------------------------------------------------------------------------
bmeta = DATA["building"]
building = Building.search(
    [("site_id", "=", site.id), ("code", "=", bmeta["code"])], limit=1
) or Building.search([("site_id", "=", site.id), ("name", "=", bmeta["name"])], limit=1)
if not building:
    building = Building.create(
        {
            "name": bmeta["name"],
            "code": bmeta["code"],
            "site_id": site.id,
            "status": "active",
        }
    )
    print("BUILDING created", building.id)
else:
    building.write({"name": bmeta["name"], "code": bmeta["code"], "status": "active"})
    print("BUILDING existing", building.id)

# ---------------------------------------------------------------------------
# 3) Floors
# ---------------------------------------------------------------------------
floor_by_name = {}
floor_by_code = {}
for fmeta in DATA["floors"]:
    floor = Floor.search(
        [("building_id", "=", building.id), ("code", "=", fmeta["code"])], limit=1
    ) or Floor.search(
        [("building_id", "=", building.id), ("floor_number", "=", fmeta["floor_number"])],
        limit=1,
    )
    vals = {
        "name": fmeta["name"],
        "code": fmeta["code"],
        "building_id": building.id,
        "floor_number": fmeta["floor_number"],
        "status": "active",
    }
    if not floor:
        floor = Floor.create(vals)
        stats["floors_created"] += 1
    else:
        floor.write(vals)
        stats["floors_existing"] += 1
    floor_by_name[fmeta["name"]] = floor
    floor_by_code[fmeta["code"]] = floor

print(
    "FLOORS created=%s existing=%s" % (stats["floors_created"], stats["floors_existing"])
)

# ---------------------------------------------------------------------------
# 4) Spaces (floor.area) — linked to floors; patrols are built from these
# ---------------------------------------------------------------------------
area_by_code = {a.code: a for a in Area.search([("site_id", "=", site.id)])}
areas_to_create = []
space_floor_map = {}  # code -> floor

for sp in DATA["spaces"]:
    floor = floor_by_name.get(sp["floor_name"])
    if not floor:
        parts = sp["code"].split("-")
        fcode = parts[1] if len(parts) >= 3 else ""
        floor = floor_by_code.get(fcode)
    if not floor:
        stats["errors"].append("No floor for space %s (%s)" % (sp["code"], sp["floor_name"]))
        continue
    space_floor_map[sp["code"]] = floor

    vals = {
        "name": sp["name"],
        "code": sp["code"],
        "floor_id": floor.id,
        "area_type": _area_type_from_code(sp["code"]),
        "status": "active",
        "active": True,
        "notes": sp.get("notes") or False,
    }
    existing = area_by_code.get(sp["code"])
    if existing:
        existing.write(
            {
                "name": vals["name"],
                "floor_id": floor.id,
                "area_type": vals["area_type"],
                "status": "active",
                "active": True,
                "notes": vals["notes"],
            }
        )
        stats["areas_updated"] += 1
    else:
        areas_to_create.append(vals)

if areas_to_create:
    chunk = 100
    for i in range(0, len(areas_to_create), chunk):
        created = Area.create(areas_to_create[i : i + chunk])
        stats["areas_created"] += len(created)
        for a in created:
            area_by_code[a.code] = a
        env.cr.commit()
        print(
            "  areas progress %s/%s"
            % (min(i + chunk, len(areas_to_create)), len(areas_to_create))
        )

print(
    "AREAS/SPACES created=%s updated=%s"
    % (stats["areas_created"], stats["areas_updated"])
)
area_by_code = {a.code: a for a in Area.search([("site_id", "=", site.id)])}

# ---------------------------------------------------------------------------
# 5) Checkpoints — one QR stop per space, linked to floor + area
# ---------------------------------------------------------------------------
scan_type = DATA.get("defaults", {}).get("scan_type", "qr")
cp_by_code = {
    c.code: c for c in Checkpoint.search([("site_id", "=", site.id)])
}

to_create = []
for sp in DATA["spaces"]:
    floor = space_floor_map.get(sp["code"]) or floor_by_name.get(sp["floor_name"])
    area = area_by_code.get(sp["code"])
    if not floor or not area:
        if sp["code"] not in space_floor_map:
            # already logged under spaces
            pass
        else:
            stats["errors"].append("Missing area/floor for checkpoint %s" % sp["code"])
        continue

    vals = {
        "name": sp["name"],
        "code": sp["code"],
        "site_id": site.id,
        "building_id": building.id,
        "floor_id": floor.id,
        "area_id": area.id,
        "scan_type": scan_type,
        "status": "active",
        "location_description": sp.get("notes") or False,
        "qr_code": sp["code"],  # printable, stable QR payload = space code
    }
    existing = cp_by_code.get(sp["code"])
    if existing:
        existing.write(
            {
                "name": vals["name"],
                "building_id": building.id,
                "floor_id": floor.id,
                "area_id": area.id,
                "scan_type": scan_type,
                "status": "active",
                "location_description": vals["location_description"],
                "qr_code": vals["qr_code"],
            }
        )
        stats["checkpoints_updated"] += 1
    else:
        to_create.append(vals)

if to_create:
    # create in chunks
    chunk = 100
    for i in range(0, len(to_create), chunk):
        created = Checkpoint.create(to_create[i : i + chunk])
        stats["checkpoints_created"] += len(created)
        for c in created:
            cp_by_code[c.code] = c
        env.cr.commit()
        print("  checkpoints progress %s/%s" % (min(i + chunk, len(to_create)), len(to_create)))

print(
    "CHECKPOINTS created=%s updated=%s"
    % (stats["checkpoints_created"], stats["checkpoints_updated"])
)

# refresh map
cp_by_code = {c.code: c for c in Checkpoint.search([("site_id", "=", site.id)])}

# ---------------------------------------------------------------------------
# 6) Tours — ordered checkpoint stops (each stop = a floor space)
# ---------------------------------------------------------------------------
for tmeta in DATA["tours"]:
    tour = Tour.search([("code", "=", tmeta["code"])], limit=1)
    desc = "Schedule: %s | Assigned guard (sheet): %s | Coverage: %s" % (
        tmeta.get("time") or "",
        tmeta.get("guard") or "",
        tmeta.get("coverage") or "",
    )
    vals = {
        "name": tmeta["name"],
        "code": tmeta["code"],
        "site_id": site.id,
        "building_id": building.id,
        "description": desc,
        "estimated_duration": tmeta.get("estimated_duration") or 1.0,
        "frequency": "daily",
        "status": "draft",
    }
    if not tour:
        tour = Tour.create(vals)
        stats["tours_created"] += 1
    else:
        tour.write(vals)
        stats["tours_updated"] += 1

    # Rebuild ordered lines
    missing = []
    ordered_ids = []
    for stop in tmeta["stops"]:
        cp = cp_by_code.get(stop["code"])
        if not cp:
            missing.append(stop["code"])
            continue
        ordered_ids.append(cp.id)
    if missing:
        stats["errors"].append(
            "%s missing checkpoints: %s" % (tmeta["code"], ", ".join(missing[:10]))
        )
    tour._rebuild_checkpoint_lines(ordered_ids)
    tour.write({"status": "active"})
    env.cr.commit()
    print(
        "TOUR %s lines=%s missing=%s"
        % (tmeta["code"], len(ordered_ids), len(missing))
    )

# ---------------------------------------------------------------------------
# 7) Guards
# ---------------------------------------------------------------------------
portal_group = env.ref("guardpro.group_guardpro_guard_portal")
# Sheet "Supervisor" is noted on profile; portal users cannot also be internal supervisors.

for umeta in DATA["users"]:
    email = umeta["email"].strip().lower()
    user = Users.search([("login", "=", email)], limit=1)
    phone = _normalize_phone(umeta.get("mobile"))

    if not user:
        # create portal user + partner
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
        print("USER created", email)
    else:
        # ensure site assignment + group
        writes = {}
        if portal_group not in user.groups_id and not user.has_group("base.group_user"):
            writes["groups_id"] = [(4, portal_group.id)]
        site_ids = user.site_ids.ids
        if site.id not in site_ids:
            writes["site_ids"] = [(4, site.id)]
        if writes:
            user.write(writes)
        if phone and not (user.partner_id.phone or user.partner_id.mobile):
            user.partner_id.write({"phone": phone, "mobile": phone})
        print("USER existing", email)

    guard = Guard.search([("user_id", "=", user.id)], limit=1) or Guard.search(
        [("name", "=ilike", umeta["name"])], limit=1
    )
    guard_vals = {
        "name": umeta["name"],
        "user_id": user.id,
        "phone": phone or False,
        "status": "active",
        "availability": "full_time",
        "current_site_id": site.id,
    }
    # shift hint in notes if field exists
    if "notes" in Guard._fields:
        guard_vals["notes"] = "%s shift — %s" % (umeta.get("shift") or "", umeta.get("role") or "")

    if not guard:
        guard = Guard.with_context(
            mail_notrack=True,
            mail_create_nolog=True,
            mail_create_nosubscribe=True,
        ).create(guard_vals)
        stats["guards_created"] += 1
        print("GUARD created", guard.name, guard.badge_number)
    else:
        guard.with_context(mail_notrack=True).write(
            {
                "name": umeta["name"],
                "user_id": user.id,
                "phone": phone or guard.phone,
                "status": "active",
                "current_site_id": site.id,
            }
        )
        stats["guards_existing"] += 1
        print("GUARD existing", guard.name, guard.badge_number)

env.cr.commit()

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("==== DONE ====")
print(
    json.dumps(
        {
            **stats,
            "site_id": site.id,
            "building_id": building.id,
            "floor_count": Floor.search_count([("building_id", "=", building.id)]),
            "area_count": Area.search_count([("site_id", "=", site.id)]),
            "checkpoint_count": Checkpoint.search_count([("site_id", "=", site.id)]),
            "tour_count": Tour.search_count([("site_id", "=", site.id)]),
            "guard_count_on_site": Users.search_count([("site_ids", "in", [site.id])]),
        },
        indent=2,
    )
)
