# eSign Application - Features & Workflows Documentation

## 1. Executive Summary
The **eSign Application** is a comprehensive, enterprise-grade document generation and electronic signature platform. Built to digitize, streamline, and secure internal approval processes, it allows employees to request, review, and digitally sign documents utilizing dynamic multi-stage approval workflows. The platform prioritizes high-fidelity document reproduction, cryptographic integrity, and a robust audit trail.

## 2. Core Features

### 2.1. Authentication and Security
*   **Single Sign-On (SSO):** Integration with Microsoft Entra ID allows users to securely log in using organizational Microsoft accounts.
*   **Role-Based Access Control (RBAC):** Granular permissions (Admin, User) and scopes (Global, Departmental, Own) dictate access to master data, templates, and sensitive requests.
*   **Security Auditing:** Every system event—from login attempts to administrative configuration changes—is recorded in a comprehensive audit trail, capturing the user's identity, action, resource ID, and **originating client IP address**.
*   **Document Integrity (Hashing):** The system calculates and stores a **SHA-256 cryptographic hash** of the document at every signing step. This ensures that any tempering outside the application can be immediately identified.

### 2.2. Master Data & Template Management
*   **Organizational Mapping:** Admins define Departments and Document Types to establish clear logical boundaries.
*   **PDF Template Builder:** Import existing PDF forms and overlay drag-and-drop placeholders for text, dates, and signers.
*   **Dynamic Layout Templates:** JSON-based templates for flexible document structure generation and automated field binding.

### 2.3. Advanced Approval Workflow Engine
*   **Sequential Chains:** Enforces a strict order of operations (e.g., Step 1 must sign before Step 2 is notified).
*   **Delegated Authority:** Allows users to delegate their signing responsibility to another authorized user (useful for leave or organizational changes).
*   **Rejection & Feedback:** Signers can reject a request with detailed comments, triggering a notification back to the requester for correction.
*   **Automated Reminders:** A built-in service pings pending approvers who haven't acted within 24 hours to ensure workflow momentum.

### 2.4. Digital Signature & PDF Processing
*   **Multi-Modal Signing:** Support for drawing signatures, uploading images, or utilizing saved profile signatures/initials.
*   **High-Fidelity Embedding:** Authentic user signatures are permanently injected into the PDF as verifiable image assets at exact mathematical coordinates.
*   **Visual Workflow Stepper:** Replaces complex text statuses with an intuitive visual progress bar, showing exactly where a document is in the (Requester ➔ Manager ➔ Finance ➔ Completed) chain.

### 2.5. Storage, Archiving & Compliance
*   **Azure Blob Storage:** Documents are stored in secure Azure containers using **persistent blob path storage**.
*   **Short-Lived SAS Security:** Document viewing links are generated strictly on-demand with a **30-minute expiry**, preventing the exposure of long-lived URLs.
*   **Bulk Archiving:** Administrators can manage high volumes of requests by archiving multiple documents simultaneously, maintaining a clean dashboard while preserving audit trails.

---

## 3. Key System Workflows

### Workflow 1: Admin Configuration
1.  **Definitions:** Admin defines Departments and Document Types.
2.  **Templates:** Admin uploads a PDF and maps signature boxes for specific roles (e.g., "HR Manager", "COO").
3.  **Workflow Mapping:** Ties a sequential list of roles/emails to the template (e.g., 1. Dept Head -> 2. Finance).
4.  **SMTP Setup:** Configures the SendGrid or SMTP relay for automated notifications.

### Workflow 2: Request Submission
1.  **Initiation:** User selects a template and fills in the dynamic web-form attributes.
2.  **Preview:** The system generates a watermarked draft PDF for visual verification.
3.  **Submission:** The backend locks the initial state, calculates the first hash, and alerts the first person in the chain.

### Workflow 3: Signing & Chain Advancement
1.  **Notification:** Approver receives an email with an authorized link.
2.  **Authentication:** Upon login, the system generates a **secure short-lived SAS token** for document viewing.
3.  **Interaction:** Approver signs or rejects with comments.
4.  **Processing:** If signed, the PDF is manipulated in the backend, a new hash is recorded, the file is pushed to Azure, and the next person in the sequence is pinged.

---

## 4. Technical Architecture Stack

*   **Frontend:** React/Next.js SPA utilizing TailwindCSS. Features modular components (RequestTable, WorkflowStepper, AuditLogViewer) for high maintainability.
*   **Backend Server:** High-concurrency **FastAPI** (Python). Refactored into modular **Routers** (Requests, Auth, Admin, Templates) and **Services** (PDF Engine, Blob, Audit, Email).
*   **Document Core:** **PyMuPDF (Fitz)** for low-level PDF manipulation; **DocxTpl** for dynamic Word-to-PDF generation.
*   **Database & Storage:** SQLAlchemy ORM (Data Layer) and Azure Storage SDK (Secure File Persistence).

---
*Authorized for internal review and management capability assessments.*
