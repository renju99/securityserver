# Implementation Plan - eSign App Enhancements

This plan outlines the steps to implement the four suggested improvements for the eSign application: Architectural Refactoring, Enhanced Security, Workflow Enhancements, and UX Improvements.

## 1. Architectural Refactoring (Backend & Frontend)

### Phase 1: Backend Modularization
- Create `backend/routers/` directory for API endpoints.
- Create `backend/services/` directory for business logic (PDF engine, Azure Blob, Email).
- **Sub-tasks:**
    - [ ] `routers/auth.py`: Microsoft SSO and local login logic.
    - [ ] `routers/templates.py`: PDF and Dynamic template management.
    - [ ] `routers/requests.py`: Document request lifecycle.
    - [ ] `routers/admin.py`: Master data, users, and email config.
    - [ ] `services/pdf_service.py`: Refactor PyMuPDF logic from `main.py`.
    - [ ] `services/blob_service.py`: Refactor Azure storage logic.

### Phase 2: Frontend Componentization
- Deconstruct `frontend/src/app/page.tsx` into reusable components.
- **Sub-tasks:**
    - [ ] `components/Dashboard/`: Request list, filters, and search.
    - [ ] `components/Requests/`: New request form, previewer, and signature pad.
    - [ ] `components/Admin/`: Template builder, workflow mapper, and logs.
    - [ ] `lib/api/`: Create an API client service to handle all fetch calls.

## 2. Enhanced Security & Compliance

### Phase 3: Audit Logging & Hashing
- [ ] **Database Updates:** Add `AuditLog` model to `models.py`.
- [ ] **Implementation:**
    - Create a middleware or utility to log actions: `log_event(user_id, action, resource_id, metadata)`.
    - Implement SHA-256 hashing for PDFs after each signing step.
    - Store hashes in a new `DocumentVersion` or `SignatureHash` table.
- [ ] **SAS Optimization:** Ensure SAS tokens are short-lived and generated just-in-time.

## 3. Workflow & Feature Enhancements

### Phase 4: Advanced Workflows
- [ ] **Rejection Logic:** Allow approvers to reject with comments, resetting the request to "Draft" or a "Needs Revision" state.
- [ ] **Delegation:** Add `delegated_to` field to the User model.
- [ ] **Bulk Actions:** Implement UI and Backend logic for bulk signing/archiving.
- [ ] **Reminders:** Set up a background task (FastAPI `BackgroundTasks` or a simple worker) for email reminders.

## 4. User Experience (UX) Improvements

### Phase 5: Visual Polish & Search
- [ ] **Workflow Stepper:** Build a visual progress component for the request detail view.
- [ ] **Advanced Filters:** Implement client-side and server-side filtering for the dashboard.
- [ ] **Mobile Optimization:** Refine CSS and signature pad interactions for touch devices.
- [ ] **Dark Mode / Branding:** Finalize Tailwind configurations for a premium, consistent look.

---
**Next Step:** I will begin with Phase 1 (Backend Modularization) and Phase 3 (Database Updates for Audit Logs) simultaneously to ensure the new architecture supports the security features.
