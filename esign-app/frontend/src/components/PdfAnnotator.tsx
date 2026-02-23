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
    type: 'signature' | 'initial' | 'date' | 'name' | 'text';
    page: number;
    x: number; // Percentage
    y: number; // Percentage
    width: number; // Percentage
    height: number; // Percentage
    assignee: string; // User email
}

const FIELD_TOOLS = [
    { type: 'signature', label: 'Signature', icon: '✒️' },
    { type: 'initial', label: 'Initials', icon: '✍️' },
    { type: 'date', label: 'Date', icon: '📅' },
    { type: 'name', label: 'Full Name', icon: '👤' },
    { type: 'text', label: 'Text Field', icon: '📝' },
] as const;

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
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);
    const [draggedTool, setDraggedTool] = useState<typeof FIELD_TOOLS[number]['type'] | null>(null);
    const [activeTool, setActiveTool] = useState<typeof FIELD_TOOLS[number]['type']>('signature');
    const [scale, setScale] = useState(1.0);

    const [containerWidth, setContainerWidth] = useState(800);
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const updateWidth = () => {
            if (containerRef.current) {
                const padding = window.innerWidth < 768 ? 20 : 64;
                const newWidth = Math.min(containerRef.current.offsetWidth - padding, 800);
                setContainerWidth(newWidth > 0 ? newWidth : 300);
            }
        };

        updateWidth();
        window.addEventListener('resize', updateWidth);
        return () => window.removeEventListener('resize', updateWidth);
    }, [loading]); // Re-run when loading finishes

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

    // --- Drag and Drop Tools Logic ---
    const handleToolDrop = (e: React.DragEvent, pageIndex: number) => {
        e.preventDefault();
        if (!draggedTool) return;

        const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
        const x = ((e.clientX - rect.left) / rect.width) * 100;
        const y = ((e.clientY - rect.top) / rect.height) * 100;

        const defaultWidth = draggedTool === 'signature' ? 25 : draggedTool === 'initial' ? 10 : 15;
        const defaultHeight = draggedTool === 'date' ? 4 : 8;

        const newField: SignatureField = {
            id: crypto.randomUUID(),
            type: draggedTool,
            page: pageIndex + 1,
            x: Math.min(Math.max(x - (defaultWidth / 2), 0), 100 - defaultWidth),
            y: Math.min(Math.max(y - (defaultHeight / 2), 0), 100 - defaultHeight),
            width: defaultWidth,
            height: defaultHeight,
            assignee: ''
        };

        setFields([...fields, newField]);
        setSelectedField(newField.id);
        setDraggedTool(null);
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
            type: activeTool,
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
                <div className="flex items-center gap-4">
                    <button
                        onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                        className="lg:hidden p-2 text-gray-500 hover:bg-gray-100 rounded-md"
                    >
                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" /></svg>
                    </button>
                    <div>
                        <Link href="/" className="text-gray-500 hover:text-gray-900 text-sm font-bold mb-1 block">← Back</Link>
                        <h1 className="text-lg md:text-2xl font-black text-gray-900 truncate max-w-[150px] md:max-w-none">{templateName}</h1>
                    </div>
                </div>
                <div className="flex items-center space-x-2 md:space-x-4">
                    <div className="flex items-center bg-gray-100 rounded-lg p-1 mr-4">
                        <button
                            onClick={() => setScale(Math.max(0.5, scale - 0.1))}
                            className="p-1 px-3 hover:bg-white rounded-md text-gray-600 transition-all font-bold"
                        >
                            -
                        </button>
                        <span className="text-xs font-black text-gray-500 w-12 text-center">
                            {Math.round(scale * 100)}%
                        </span>
                        <button
                            onClick={() => setScale(Math.min(2.5, scale + 0.1))}
                            className="p-1 px-3 hover:bg-white rounded-md text-gray-600 transition-all font-bold"
                        >
                            +
                        </button>
                    </div>
                    <button
                        onClick={handleSave}
                        disabled={isSaving}
                        className="bg-indigo-600 text-white px-3 md:px-6 py-2 rounded-lg text-xs md:text-sm font-bold hover:bg-indigo-700 disabled:opacity-50"
                    >
                        {isSaving ? 'Saving...' : 'Save'}
                    </button>
                </div>
            </div>

            <div className="flex-1 flex">
                {/* Sidebar Controls */}
                <div className={`fixed inset-y-0 left-0 transform ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full'} lg:relative lg:translate-x-0 transition duration-200 ease-in-out z-30 w-80 bg-white border-r p-6 overflow-y-auto pt-24 lg:pt-6`}>
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

                    <div className="mb-8">
                        <h3 className="font-bold text-gray-900 mb-4 uppercase text-xs tracking-wider">Signature Tools</h3>
                        <div className="grid grid-cols-1 gap-2">
                            {FIELD_TOOLS.map(tool => (
                                <div
                                    key={tool.type}
                                    draggable
                                    onDragStart={() => setDraggedTool(tool.type)}
                                    onClick={() => setActiveTool(tool.type)}
                                    className={`flex items-center gap-3 p-3 bg-white border-2 border-dashed rounded-xl transition-all group cursor-pointer
                                      ${activeTool === tool.type ? 'border-indigo-600 bg-indigo-50 shadow-sm' : 'border-gray-200 hover:border-indigo-400 hover:bg-indigo-50'}
                                    `}
                                >
                                    <span className="text-xl">{tool.icon}</span>
                                    <span className={`text-xs font-black tracking-tight group-hover:text-indigo-700 ${activeTool === tool.type ? 'text-indigo-900' : 'text-gray-600'}`}>{tool.label}</span>
                                </div>
                            ))}
                        </div>
                    </div>

                    <h3 className="font-bold text-gray-900 mb-4 uppercase text-xs tracking-wider">Signature Fields</h3>
                    {fields.length === 0 && <p className="text-gray-400 text-sm">Click on the document to add a signature box.</p>}
                    <div className="space-y-3">
                        {fields.map((f, idx) => {
                            const tool = FIELD_TOOLS.find(t => t.type === f.type);
                            return (
                                <div
                                    key={f.id}
                                    className={`p-3 rounded-lg border cursor-pointer hover:border-indigo-300 ${selectedField === f.id ? 'border-indigo-600 bg-indigo-50' : 'border-gray-200'}`}
                                    onClick={() => setSelectedField(f.id)}
                                >
                                    <div className="flex justify-between items-center mb-2">
                                        <span className="font-bold text-xs text-gray-700 flex items-center gap-1">
                                            {tool?.icon} {tool?.label} (Page {f.page})
                                        </span>
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
                <div ref={containerRef} className="flex-1 bg-gray-100 p-4 md:p-8 overflow-auto flex justify-center">
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
                                    onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; }}
                                    onDrop={(e) => handleToolDrop(e, index)}
                                >
                                    <Page
                                        pageNumber={index + 1}
                                        width={containerWidth * scale}
                                        renderAnnotationLayer={false}
                                        renderTextLayer={false}
                                    />

                                    {/* Overlay for fields */}
                                    {fields.filter(f => f.page === index + 1).map(f => {
                                        const tool = FIELD_TOOLS.find(t => t.type === f.type);
                                        const fieldUser = users.find(u => u.email === f.assignee);
                                        const label = fieldUser ? fieldUser.full_name : (f.assignee || (tool ? tool.label : 'Unassigned'));
                                        return (
                                            <div
                                                key={f.id}
                                                className={`signature-field absolute border-2 flex flex-col items-center justify-center text-[10px] font-black cursor-move transition-all rounded-lg overflow-hidden
                                        ${selectedField === f.id ? 'border-indigo-600 bg-white shadow-xl z-20' : 'border-blue-400 bg-white/90 z-10'}
                                    `}
                                                style={{
                                                    left: `${f.x}%`,
                                                    top: `${f.y}%`,
                                                    width: `${f.width}%`,
                                                    height: `${f.height}%`
                                                }}
                                                onMouseDown={(e) => handleInteractionStart(e, f.id, 'move')}
                                                onClick={(e) => { e.stopPropagation(); setSelectedField(f.id); }}
                                                title={`Type: ${f.type}, Role: ${f.assignee}`}
                                            >
                                                <div className={`w-full text-center py-0.5 ${selectedField === f.id ? 'bg-indigo-600 text-white' : 'bg-blue-400 text-white'}`}>
                                                    {tool?.icon} {f.type.toUpperCase()}
                                                </div>
                                                <div className="flex-1 flex items-center justify-center px-1 text-center leading-none">
                                                    {label}
                                                </div>

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
