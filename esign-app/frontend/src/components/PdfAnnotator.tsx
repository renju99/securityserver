'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import Link from 'next/link';

// Configure Worker
pdfjs.GlobalWorkerOptions.workerSrc = `/pdf.worker.min.mjs`;

interface SignatureField {
    id: string;
    page: number;
    x: number; // Percentage
    y: number; // Percentage
    width: number; // Percentage
    height: number; // Percentage
    assignee: string; // User email
}

interface User {
    id: number;
    email: string;
    full_name: string;
    role: string;
}

export default function PdfAnnotator() {
    const searchParams = useSearchParams();
    const router = useRouter();
    const templateName = searchParams.get('template');

    const [fileUrl, setFileUrl] = useState<string | null>(null);
    const [numPages, setNumPages] = useState<number | null>(null);
    const [fields, setFields] = useState<SignatureField[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedField, setSelectedField] = useState<string | null>(null);
    const [isSaving, setIsSaving] = useState(false);

    const [users, setUsers] = useState<User[]>([]);
    const [departments, setDepartments] = useState<{ id: number; name: string }[]>([]);
    const [docTypes, setDocTypes] = useState<{ id: number; name: string }[]>([]);
    const [selectedDept, setSelectedDept] = useState('');
    const [selectedDocType, setSelectedDocType] = useState('');

    // Track if we are currently dragging/resizing to prevent click-to-create
    const interactionRef = useRef(false);

    // Load PDF URL, existing config, and users
    useEffect(() => {
        if (!templateName) return;

        const init = async () => {
            try {
                // Parallel fetch: File Link, Template Config, Users, Master Data
                const [sasRes, tplRes, usersRes, deptsRes, typesRes] = await Promise.all([
                    fetch(`/api/get-link/${encodeURIComponent(templateName)}`),
                    fetch('/api/pdf-templates'),
                    fetch('/api/users'),
                    fetch('/api/departments'),
                    fetch('/api/document-types')
                ]);

                if (!sasRes.ok) throw new Error("Failed to get file link");
                const sasData = await sasRes.json();
                setFileUrl(sasData.url);



                if (usersRes.ok) {
                    const usersData = await usersRes.json();
                    setUsers(usersData);
                }

                if (deptsRes.ok) setDepartments(await deptsRes.json());
                if (typesRes.ok) setDocTypes(await typesRes.json());

                // Set initial values if template exists
                if (tplRes.ok) {
                    const templates = await tplRes.json();
                    const existing = templates.find((t: any) => t.name === templateName);
                    if (existing) {
                        if (existing.department) setSelectedDept(existing.department);
                        if (existing.doc_type) setSelectedDocType(existing.doc_type);
                        if (existing.form_fields) setFields(existing.form_fields);
                    }
                }

            } catch (err) {
                console.error(err);
                alert("Error loading template data");
            } finally {
                setLoading(false);
            }
        };
        init();
    }, [templateName]);

    const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
        setNumPages(numPages);
    };

    // --- Drawing Logic ---
    const [drawing, setDrawing] = useState<{ startX: number; startY: number; currentX: number; currentY: number; pageIndex: number } | null>(null);

    const handleMouseDown = (e: React.MouseEvent, pageIndex: number) => {
        if (interactionRef.current) return;
        if ((e.target as HTMLElement).closest('.signature-field')) return;

        const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
        const x = ((e.clientX - rect.left) / rect.width) * 100;
        const y = ((e.clientY - rect.top) / rect.height) * 100;

        setDrawing({ startX: x, startY: y, currentX: x, currentY: y, pageIndex });
    };

    const handleMouseMove = (e: React.MouseEvent) => {
        if (!drawing) return;

        const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
        const x = ((e.clientX - rect.left) / rect.width) * 100;
        const y = ((e.clientY - rect.top) / rect.height) * 100;

        setDrawing({ ...drawing, currentX: x, currentY: y });
    };

    const handleMouseUp = (e: React.MouseEvent, pageIndex: number) => {
        if (!drawing) return;
        if (drawing.pageIndex !== pageIndex) {
            setDrawing(null);
            return;
        }

        const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
        const endX = ((e.clientX - rect.left) / rect.width) * 100;
        const endY = ((e.clientY - rect.top) / rect.height) * 100;

        const width = Math.abs(endX - drawing.startX);
        const height = Math.abs(endY - drawing.startY);
        const x = Math.min(drawing.startX, endX);
        const y = Math.min(drawing.startY, endY);

        // Minimum size check (e.g., 1% width/height) to avoid accidental clicks creating tiny specks
        if (width < 1 || height < 1) {
            setDrawing(null);
            return;
        }

        const newField: SignatureField = {
            id: crypto.randomUUID(),
            page: pageIndex + 1,
            x,
            y,
            width,
            height,
            assignee: ''
        };

        setFields([...fields, newField]);
        setSelectedField(newField.id);
        setDrawing(null);
    };

    // --- Drag and Resize Logic ---

    // Generalized handler for both moving and resizing
    const handleInteractionStart = (e: React.MouseEvent, id: string, mode: 'move' | 'resize') => {
        e.stopPropagation(); // Crucial: Stop click from bubbling to page
        e.preventDefault(); // Prevent text selection etc.

        const field = fields.find(f => f.id === id);
        if (!field) return;

        setSelectedField(id); // Ensure selected

        const startX = e.clientX;
        const startY = e.clientY;
        const startLeft = field.x;
        const startTop = field.y;
        const startWidth = field.width;
        const startHeight = field.height;

        // Container is the page div
        const container = (e.currentTarget.closest('.react-pdf__Page') as HTMLElement).getBoundingClientRect();

        interactionRef.current = true;

        const onMouseMove = (moveEvent: MouseEvent) => {
            moveEvent.preventDefault();
            const deltaXPx = moveEvent.clientX - startX;
            const deltaYPx = moveEvent.clientY - startY;

            // Convert pixel delta to percentage delta
            const deltaXPercent = (deltaXPx / container.width) * 100;
            const deltaYPercent = (deltaYPx / container.height) * 100;

            setFields(prev => prev.map(f => {
                if (f.id !== id) return f;

                if (mode === 'move') {
                    // Update Position
                    return {
                        ...f,
                        x: Math.min(Math.max(startLeft + deltaXPercent, 0), 100 - f.width),
                        y: Math.min(Math.max(startTop + deltaYPercent, 0), 100 - f.height)
                    };
                } else {
                    // Update Size
                    return {
                        ...f,
                        width: Math.max(5, startWidth + deltaXPercent),
                        height: Math.max(2, startHeight + deltaYPercent)
                    };
                }
            }));
        };

        const onMouseUp = () => {
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
            // Delay clearing the flag to avoid triggering onClick immediately after mouseup
            setTimeout(() => {
                interactionRef.current = false;
            }, 100);
        };

        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    };


    const handleFieldUpdate = (id: string, updates: Partial<SignatureField>) => {
        setFields(fields.map(f => f.id === id ? { ...f, ...updates } : f));
    };

    const handleDeleteField = (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        setFields(fields.filter(f => f.id !== id));
        setSelectedField(null);
    };

    const handleSave = async () => {
        if (!templateName || !fileUrl) return;
        setIsSaving(true);
        try {
            const listRes = await fetch('/api/pdf-templates');
            const list = await listRes.json();
            const existing = list.find((t: any) => t.name === templateName);

            if (existing) {
                await fetch(`/api/pdf-templates/${existing.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: templateName,
                        name: templateName,
                        form_fields: fields,
                        department: selectedDept,
                        doc_type: selectedDocType
                    })
                });
            } else {
                await fetch('/api/pdf-templates', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: templateName,
                        blob_url: fileUrl.split('?')[0],
                        name: templateName,
                        form_fields: fields,
                        department: selectedDept,
                        doc_type: selectedDocType
                    })
                });
            }
            alert("Configuration saved!");
        } catch (e) {
            console.error("Save Error:", e);
            alert("Save failed: " + (e as Error).message);
        } finally {
            setIsSaving(false);
        }
    };

    if (loading) return <div className="p-10 text-center">Loading...</div>;

    const currentField = fields.find(f => f.id === selectedField);

    return (
        <div className="min-h-screen bg-gray-50 flex flex-col">
            {/* Header */}
            <div className="bg-white border-b px-8 py-4 flex justify-between items-center sticky top-0 z-50">
                <div>
                    <Link href="/" className="text-gray-500 hover:text-gray-900 text-sm font-bold mb-1 block">← Back to Dashboard</Link>
                    <h1 className="text-2xl font-black text-gray-900">{templateName}</h1>
                </div>
                <div className="flex space-x-4">
                    <button
                        onClick={handleSave}
                        disabled={isSaving}
                        className="bg-indigo-600 text-white px-6 py-2 rounded-lg font-bold hover:bg-indigo-700 disabled:opacity-50"
                    >
                        {isSaving ? 'Saving...' : 'Save Configuration'}
                    </button>
                    <a
                        href={fileUrl ?? '#'}
                        target="_blank"
                        className="bg-white border border-gray-300 text-gray-700 px-4 py-2 rounded-lg font-bold hover:bg-gray-50"
                    >
                        View Original
                    </a>
                </div>
            </div>

            <div className="flex-1 flex">
                {/* Sidebar Controls */}
                <div className="w-80 bg-white border-r p-6 overflow-y-auto">
                    <div className="mb-8 p-4 bg-gray-50 rounded-lg border border-gray-200">
                        <h3 className="font-bold text-gray-900 mb-4 uppercase text-xs tracking-wider">Template Settings</h3>

                        <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Department</label>
                        <select
                            value={selectedDept}
                            onChange={(e) => setSelectedDept(e.target.value)}
                            className="w-full text-sm border-gray-300 rounded-md shadow-sm mb-3"
                        >
                            <option value="">Select Department</option>
                            {departments.map(d => <option key={d.id} value={d.name}>{d.name}</option>)}
                        </select>

                        <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Document Type</label>
                        <select
                            value={selectedDocType}
                            onChange={(e) => setSelectedDocType(e.target.value)}
                            className="w-full text-sm border-gray-300 rounded-md shadow-sm"
                        >
                            <option value="">Select Type</option>
                            {docTypes.map(t => <option key={t.id} value={t.name}>{t.name}</option>)}
                        </select>
                    </div>

                    <h3 className="font-bold text-gray-900 mb-4 uppercase text-xs tracking-wider">Signature Fields</h3>
                    {fields.length === 0 && <p className="text-gray-400 text-sm">Click on the document to add a signature box.</p>}
                    <div className="space-y-3">
                        {fields.map((f, idx) => {
                            const assigneeUser = users.find(u => u.email === f.assignee);
                            return (
                                <div
                                    key={f.id}
                                    className={`p-3 rounded-lg border cursor-pointer hover:border-indigo-300 ${selectedField === f.id ? 'border-indigo-600 bg-indigo-50' : 'border-gray-200'}`}
                                    onClick={() => setSelectedField(f.id)}
                                >
                                    <div className="flex justify-between items-center mb-2">
                                        <span className="font-bold text-sm text-gray-700">Field #{idx + 1} (Page {f.page})</span>
                                        <button onClick={(e) => handleDeleteField(f.id, e)} className="text-red-400 hover:text-red-600">×</button>
                                    </div>
                                    <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Role / Placeholder</label>
                                    <select
                                        value={f.assignee || ''}
                                        onChange={(e) => handleFieldUpdate(f.id, { assignee: e.target.value })}
                                        className="w-full text-sm border-gray-300 rounded-md shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                                    >
                                        <option value="">Select User / Placeholder</option>
                                        {users.map(u => (
                                            <option key={u.id} value={u.email}>
                                                {u.full_name} ({u.role})
                                            </option>
                                        ))}
                                    </select>
                                </div>
                            );
                        })}
                    </div>
                </div>

                {/* Main Canvas */}
                <div className="flex-1 bg-gray-100 p-8 overflow-auto flex justify-center">
                    <div className="relative shadow-2xl">
                        <Document
                            file={fileUrl}
                            onLoadSuccess={onDocumentLoadSuccess}
                            loading={<div className="p-10 bg-white">Loading PDF...</div>}
                            error={<div className="p-10 bg-red-50 text-red-500">Failed to load PDF.</div>}
                        >
                            {Array.from(new Array(numPages), (el, index) => (
                                <div
                                    key={`page_${index + 1}`}
                                    className="relative mb-4 group cursor-crosshair"
                                    onMouseDown={(e) => handleMouseDown(e, index)}
                                    // Attach Global MouseUp/Move handlers or local if sufficient.
                                    // For simplicity in React without global listeners, we bind to the page div.
                                    // Note: If user drags outside, it might clip. Perfect drag requires global listeners.
                                    onMouseUp={(e) => handleMouseUp(e, index)}
                                    onMouseMove={handleMouseMove}
                                >
                                    <Page
                                        pageNumber={index + 1}
                                        width={800}
                                        renderAnnotationLayer={false}
                                        renderTextLayer={false}
                                    />

                                    {/* Overlay for fields */}
                                    {fields.filter(f => f.page === index + 1).map(f => {
                                        const label = f.assignee || 'Unassigned';
                                        return (
                                            <div
                                                key={f.id}
                                                className={`signature-field absolute border-2 flex items-center justify-center text-xs font-bold cursor-move transition-all
                                        ${selectedField === f.id ? 'border-indigo-600 bg-indigo-600/20 text-indigo-900 z-20' : 'border-blue-400 bg-blue-400/10 text-blue-800 z-10'}
                                    `}
                                                style={{
                                                    left: `${f.x}%`,
                                                    top: `${f.y}%`,
                                                    width: `${f.width}%`,
                                                    height: `${f.height}%`
                                                }}
                                                onMouseDown={(e) => handleInteractionStart(e, f.id, 'move')}
                                                onClick={(e) => e.stopPropagation()} // Extra safety against creating new fields
                                                title={`Role: ${f.assignee}`}
                                            >
                                                {label}

                                                {/* Resize Handle */}
                                                {selectedField === f.id && (
                                                    <div
                                                        className="absolute bottom-0 right-0 w-4 h-4 bg-indigo-500 cursor-se-resize z-30"
                                                        onMouseDown={(e) => handleInteractionStart(e, f.id, 'resize')}
                                                    />
                                                )}

                                            </div>
                                        );
                                    })}

                                    {/* Drawing Preview */}
                                    {drawing && drawing.pageIndex === index && (
                                        <div
                                            className="absolute border-2 border-indigo-400 bg-indigo-200/30 z-20 pointer-events-none"
                                            style={{
                                                left: `${Math.min(drawing.startX, drawing.currentX)}%`,
                                                top: `${Math.min(drawing.startY, drawing.currentY)}%`,
                                                width: `${Math.abs(drawing.currentX - drawing.startX)}%`,
                                                height: `${Math.abs(drawing.currentY - drawing.startY)}%`
                                            }}
                                        />
                                    )}
                                </div>
                            ))}
                        </Document>
                    </div>
                </div>
            </div>
        </div>
    );
}
