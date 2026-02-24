export interface User {
    id: number;
    email: string;
    full_name: string;
    job_position?: string;
    role: 'Admin' | 'User';
    auth_provider: string;
    access_scope?: 'global' | 'department' | 'own';
    permissions?: {
        departments?: string[];
    };
    saved_signature_url?: string;
    saved_initials_url?: string;
}

export interface MasterData {
    id: number;
    name: string;
}

export interface DynamicTemplate {
    id: number;
    name: string;
    category: string;
    layout: Array<{
        type: string;
        label: string;
        placeholder?: string;
        width?: number;
    }>;
}

export interface Approval {
    id: number;
    role: string;
    status: 'Pending' | 'Signed' | 'Rejected';
    signed_at?: string;
    step_number: number;
}

export interface DocumentRequest {
    id: number;
    requester_name: string;
    requester_email: string;
    template_name: string;
    department: string;
    doc_type: string;
    status: string;
    created_at: string;
    current_pdf_url: string;
    approvals: Approval[];
    supporting_documents?: Array<{ name: string; url: string; size: number }>;
    form_data: Record<string, any>;
}

export interface WorkflowConfig {
    id?: number;
    department: string;
    doc_type: string;
    approvers: string[];
    signers: string[];
}

export interface PdfTemplateResponse {
    id: number;
    name: string;
    department: string;
    doc_type: string;
    form_fields: Array<{
        id: string;
        type: string;
        assignee: string;
        page: number;
        x: number;
        y: number;
        width: number;
        height: number;
    }>;
}

export interface EmailConfig {
    id: number;
    smtp_server: string;
    smtp_port: number;
    username: string;
    from_email: string;
    from_name: string;
    encryption: string;
    imap_server?: string;
    imap_port?: number;
    imap_username?: string;
    imap_ssl: boolean;
}

export interface EmailLog {
    id: number;
    recipient: string;
    subject: string;
    status: string;
    error_message?: string;
    sent_at: string;
    request_id?: number;
}

export interface AuditLog {
    id: number;
    user_email: string;
    action: string;
    resource_type: string;
    resource_id?: string;
    details?: any;
    ip_address?: string;
    timestamp: string;
}
