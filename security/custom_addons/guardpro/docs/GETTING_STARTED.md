# Chapter 1 — Get started with GuardLink

GuardLink is flexible enough to run a single site or a multi-contract control room. This chapter walks you from empty database to a working patrol loop: **sites → guards → shifts → tours → proof of patrol**.

---

## Section overview

In this chapter you will:

- Create a **client site** and baseline security settings  
- Add **guard profiles** and credentials  
- Build a **shift** so someone is on duty  
- Define **checkpoints and a tour**, then run it from the **mobile web** interface  
- See **attendance and tour logs** roll up for supervisors  

---

## Before you begin

- Odoo 18 with the **GuardLink** app installed and your user in the appropriate security groups (see [Configuration](user-guide/03-configuration.md)).  
- **Mobile web** for guards uses the browser (installable from “Add to Home Screen” on supported devices). Legacy packaged PWA assets are not used; everything runs through Odoo routes.  
- **CCTV** records may be stored for sites where cameras are configured; **live viewing is not exposed** in the standard web UI.  
- **Biometric** browser capture is not part of the default frontend; attendance and verification follow your configured workflows (manual, device, or API where enabled).  

---

## 1. Name your workspace

1. Open **GuardLink** from the main Odoo app menu.  
2. Confirm you can see menus for **Sites**, **Guards**, **Operations**, or equivalent (exact labels depend on your access group).  
3. If menus are missing, ask an administrator to add you to the correct GuardLink security group.  

---

## 2. Create your first site

1. Go to **Sites** (or **Client Sites**) and create a new record.  
2. Fill **client**, **address**, and any **geofence** or map hints your process requires.  
3. Save. This site is the anchor for shifts, tours, checkpoints, and many operational records.  

More detail: [Site setup](sites/site_setup.md).

---

## 3. Add at least one guard

1. Open **Guards** → create a **guard profile** linked to an HR employee or contact, per your process.  
2. Add **credentials** (license, medical, etc.) if your contract requires them.  
3. Confirm the guard can sign in to the **portal / mobile** URL your team uses (often `/guardpro/mobile` or your branded path).  

More detail: [Guard profiles](guards/profile_management.md).

---

## 4. Schedule a shift

1. Open **Shifts** and create a shift for your site, with start and end times.  
2. Assign the guard you created.  
3. Resolve any **conflicts** the system reports (overlap, missing credential, etc.).  

More detail: [Shift management](operations/shift_management.md).

---

## 5. Define checkpoints and a tour

1. On the site, define **checkpoints** (names, locations, scan type: QR, NFC, etc.).  
2. Build a **security tour** that orders those checkpoints into a patrol route.  
3. Optionally use the **map / route** tools to align the tour with the physical site.  

More detail: [Checkpoints](sites/checkpoints.md), [Patrols / tours](sites/patrols.md).

---

## 6. Run the tour from the field

1. On a phone or tablet, open the **mobile web** experience and sign in as the guard.  
2. Start the assigned tour and scan or confirm each checkpoint.  
3. If something fails (missed scan, incident), log it according to your SOP—often via **tasks** or **incidents**.  

---

## 7. Review proof and handover

1. Supervisors open **tour logs** and **checkpoint scans** to verify completion.  
2. **Daily activity reports** and **compliance** views summarize the shift for clients or audits.  

More detail: [Daily activity reports](compliance/reports.md).

---

## Next chapter

Continue with **[Introduction](user-guide/01-introduction.md)** for concepts, or **[Configuration](user-guide/03-configuration.md)** to tune settings before go-live.

---

## Pro tip

Treat **lists in Odoo** like Trello lists: *To plan → In progress → Done* maps well to **shifts → active patrol → closed shift** if you use stages or tags on your operational records.
