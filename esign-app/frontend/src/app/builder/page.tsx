'use client';

import React, { useState, Suspense } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';

interface TemplateBlock {
    id: string;
    type: 'text' | 'textarea' | 'date' | 'signature' | 'table';
    label: string;
    placeholder?: string;
    width: number; // 1 to 12 columns
    options?: Record<string, unknown>;
}

const COMPONENT_TYPES = [
    { type: 'text', label: 'Short Text', icon: '📝' },
    { type: 'textarea', label: 'Long Text', icon: '📋' },
    { type: 'date', label: 'Date Field', icon: '📅' },
    { type: 'signature', label: 'Signature Block', icon: '✒️' },
    { type: 'table', label: 'Data Table', icon: '📊' },
];

function TemplateBuilderContent() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const templateId = searchParams.get('id');

    const [templateName, setTemplateName] = useState('New Template');
    const [category, setCategory] = useState('General');
    const [layout, setLayout] = useState<TemplateBlock[]>([]);
    const [selectedBlockId, setSelectedBlockId] = useState<string | null>(null);
    const [isSaving, setIsSaving] = useState(false);

    React.useEffect(() => {
        if (templateId) {
            const fetchTemplate = async () => {
                try {
                    const res = await fetch(`/api/dynamic-templates/${templateId}`);
                    if (res.ok) {
                        const data = await res.json();
                        setTemplateName(data.name);
                        setCategory(data.category);
                        setLayout(data.layout.map((b: any, idx: number) => ({
                            ...b,
                            id: b.id || `loaded-${idx}`
                        })));
                    }
                } catch (e) {
                    console.error("Fetch template fail", e);
                }
            };
            fetchTemplate();
        }
    }, [templateId]);

    // Drag and Drop State
    const [draggedType, setDraggedType] = useState<string | null>(null);
    const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

    const addBlock = (type: string, index?: number) => {
        const newBlock: TemplateBlock = {
            id: Math.random().toString(36).substr(2, 9),
            type: type as TemplateBlock['type'],
            label: `New ${type.charAt(0).toUpperCase() + type.slice(1)} Field`,
            placeholder: `Enter ${type}...`,
            width: 12, // Default to full width
        };

        if (typeof index === 'number') {
            const newLayout = [...layout];
            newLayout.splice(index, 0, newBlock);
            setLayout(newLayout);
        } else {
            setLayout([...layout, newBlock]);
        }
        setSelectedBlockId(newBlock.id);
    };

    const removeBlock = (id: string) => {
        setLayout(layout.filter(b => b.id !== id));
        if (selectedBlockId === id) setSelectedBlockId(null);
    };

    const updateBlock = (id: string, updates: Partial<TemplateBlock>) => {
        setLayout(layout.map(b => b.id === id ? { ...b, ...updates } : b));
    };

    const handleDragStart = (type: string) => {
        setDraggedType(type);
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        if (draggedType) {
            addBlock(draggedType, dragOverIndex ?? undefined);
            setDraggedType(null);
            setDragOverIndex(null);
        }
    };

    const saveTemplate = async () => {
        if (!templateName) return alert('Please enter a template name');
        setIsSaving(true);
        try {
            const url = templateId ? `/api/dynamic-templates/${templateId}` : '/api/dynamic-templates';
            const method = templateId ? 'PUT' : 'POST';

            const res = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: templateName,
                    category,
                    layout: layout.map(({ type, label, placeholder, width }) => ({ type, label, placeholder, width }))
                }),
            });
            if (res.ok) {
                alert('Template saved successfully!');
                router.push('/');
            } else {
                alert('Failed to save template');
            }
        } catch (err) {
            console.error(err);
            alert('Error saving template');
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <main className="min-h-screen bg-gray-50 flex flex-col font-sans">
            {/* Top Header */}
            <header className="bg-white border-b px-8 py-4 flex justify-between items-center sticky top-0 z-30 shadow-sm">
                <div className="flex items-center space-x-4">
                    <a href="/" className="text-gray-400 hover:text-indigo-600 transition-colors">
                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
                    </a>
                    <div className="h-6 w-px bg-gray-200" />
                    <input
                        value={templateName}
                        onChange={e => setTemplateName(e.target.value)}
                        className="text-xl font-bold bg-transparent border-none focus:ring-0 text-gray-800 placeholder-gray-300 w-64"
                        placeholder="Untitled Template"
                    />
                </div>
                <div className="flex items-center space-x-3">
                    <select
                        value={category}
                        onChange={e => setCategory(e.target.value)}
                        className="text-xs bg-gray-100 border-none rounded-full px-4 py-2 text-gray-600 focus:ring-1 focus:ring-indigo-500 cursor-pointer"
                    >
                        <option value="General">General</option>
                        <option value="HR">HR</option>
                        <option value="Finance">Finance</option>
                        <option value="IT">IT</option>
                    </select>
                    <button
                        onClick={saveTemplate}
                        disabled={isSaving || layout.length === 0}
                        className="bg-indigo-600 text-white px-6 py-2 rounded-lg font-semibold hover:bg-indigo-700 transition-all shadow-md disabled:opacity-50 disabled:shadow-none"
                    >
                        {isSaving ? 'Saving...' : 'Save Template'}
                    </button>
                </div>
            </header>

            <div className="flex-1 flex overflow-hidden">
                {/* Left Sidebar: Components */}
                <aside className="w-72 bg-white border-r p-6 overflow-y-auto z-20 shadow-sm">
                    <h3 className="text-xs font-black text-gray-400 uppercase tracking-widest mb-6">Components</h3>
                    <div className="space-y-3">
                        {COMPONENT_TYPES.map(comp => (
                            <div
                                key={comp.type}
                                draggable
                                onDragStart={() => handleDragStart(comp.type)}
                                className="flex items-center space-x-3 p-3 bg-gray-50 rounded-xl border border-gray-100 hover:border-indigo-300 hover:bg-white hover:shadow-md cursor-grab active:cursor-grabbing transition-all group"
                            >
                                <span className="text-xl">{comp.icon}</span>
                                <span className="text-sm font-medium text-gray-700 group-hover:text-indigo-700">{comp.label}</span>
                            </div>
                        ))}
                    </div>

                    <div className="mt-12 p-4 bg-indigo-50 rounded-xl border border-indigo-100">
                        <h4 className="text-[10px] font-bold text-indigo-600 uppercase mb-2">Pro Tip</h4>
                        <p className="text-[10px] text-indigo-900 leading-relaxed italic">
                            Drag components onto the workspace to start designing. You can click any field to edit its properties.
                        </p>
                    </div>
                </aside>

                {/* Center: Canvas */}
                <section
                    className="flex-1 overflow-y-auto p-12 bg-gray-100 relative"
                    onDragOver={e => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; }}
                    onDrop={handleDrop}
                >
                    <div className="max-w-3xl mx-auto bg-white min-h-[1056px] shadow-2xl rounded-sm border border-gray-200 relative overflow-hidden flex flex-col">
                        {/* Template Page Header */}
                        <div className="border-b-2 border-indigo-900 p-8 flex justify-between items-center bg-white">
                            <div className="text-2xl font-black text-indigo-900 tracking-tighter">Berkeley eSign</div>
                            <div className="text-[10px] uppercase font-bold text-gray-300 italic">Dynamic Layout Engine</div>
                        </div>

                        <div className="flex-1 p-12 grid grid-cols-12 gap-y-6 gap-x-4 auto-rows-min">
                            {layout.length === 0 && (
                                <div className="flex flex-col items-center justify-center h-[400px] border-2 border-dashed border-gray-200 rounded-3xl opacity-40">
                                    <div className="text-6xl mb-4">✨</div>
                                    <p className="text-lg font-medium text-gray-400 italic">Drop components here</p>
                                </div>
                            )}

                            {layout.map((block) => (
                                <div
                                    key={block.id}
                                    onClick={() => setSelectedBlockId(block.id)}
                                    className={`relative p-5 rounded-xl border-2 transition-all cursor-pointer group flex flex-col justify-between ${selectedBlockId === block.id
                                        ? 'border-indigo-500 bg-indigo-50 shadow-sm'
                                        : 'border-transparent hover:border-gray-200 hover:bg-gray-50'
                                        }`}
                                    style={{ gridColumn: `span ${block.width || 12} / span ${block.width || 12}` }}
                                >
                                    <div className="flex justify-between items-start mb-2">
                                        <label className="text-[10px] font-black text-gray-500 uppercase tracking-tighter block">{block.label}</label>
                                        <button
                                            onClick={(e) => { e.stopPropagation(); removeBlock(block.id); }}
                                            className="text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                                        >
                                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                                        </button>
                                    </div>

                                    {block.type === 'textarea' ? (
                                        <div className="w-full h-24 bg-white border border-gray-200 rounded-lg shadow-inner pointer-events-none p-3 text-xs text-gray-300 italic">{block.placeholder}</div>
                                    ) : block.type === 'signature' ? (
                                        <div className="w-64 h-20 border-b-2 border-gray-200 flex items-end pb-1 text-[10px] text-gray-400 italic">Sign Here</div>
                                    ) : block.type === 'table' ? (
                                        <div className="border rounded-lg overflow-hidden bg-white shadow-sm pointer-events-none opacity-60">
                                            <div className="bg-gray-50 border-b p-2 grid grid-cols-4 gap-2">
                                                {[1, 2, 3, 4].map(i => <div key={i} className="h-2 bg-gray-200 rounded w-full" />)}
                                            </div>
                                            <div className="p-2 grid grid-cols-4 gap-2 border-b">
                                                {[1, 2, 3, 4].map(i => <div key={i} className="h-2 bg-gray-100 rounded w-full" />)}
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="w-full h-10 bg-white border border-gray-200 rounded-lg shadow-inner flex items-center px-4 text-xs text-gray-300 italic">{block.placeholder}</div>
                                    )}
                                </div>
                            ))}
                        </div>

                        <div className="p-12 border-t mt-auto text-center opacity-30">
                            <p className="text-[8px] font-bold text-gray-400 uppercase tracking-widest">Document Footer • Berkeley eSign Services</p>
                        </div>
                    </div>
                </section>

                {/* Right Sidebar: Properties */}
                <aside className="w-80 bg-white border-l p-8 overflow-y-auto z-20 shadow-inner">
                    <h3 className="text-xs font-black text-gray-400 uppercase tracking-widest mb-8">Properties</h3>

                    {selectedBlockId ? (
                        <div className="space-y-6 animate-in slide-in-from-right duration-300">
                            {layout.filter(b => b.id === selectedBlockId).map(block => (
                                <div key={block.id} className="space-y-5">
                                    <div className="p-4 bg-gray-50 rounded-2xl border border-gray-100 mb-6">
                                        <span className="text-xs text-gray-400 uppercase font-bold block mb-1">FIELD TYPE</span>
                                        <span className="text-sm font-bold text-indigo-700">{block.type.toUpperCase()}</span>
                                    </div>

                                    <div>
                                        <label className="block text-[10px] font-black text-gray-500 uppercase tracking-tighter mb-2">Display Label</label>
                                        <input
                                            value={block.label}
                                            onChange={e => updateBlock(block.id, { label: e.target.value })}
                                            className="w-full p-3 border-2 border-gray-100 rounded-xl focus:border-indigo-400 focus:outline-none transition-colors text-sm font-semibold text-gray-700 shadow-sm"
                                        />
                                    </div>

                                    {block.type !== 'signature' && block.type !== 'table' && (
                                        <div>
                                            <label className="block text-[10px] font-black text-gray-500 uppercase tracking-tighter mb-2">Placeholder Hint</label>
                                            <input
                                                value={block.placeholder || ''}
                                                onChange={e => updateBlock(block.id, { placeholder: e.target.value })}
                                                className="w-full p-3 border-2 border-gray-100 rounded-xl focus:border-indigo-400 focus:outline-none transition-colors text-sm text-gray-600 shadow-sm"
                                            />
                                        </div>
                                    )}

                                    <div>
                                        <label className="block text-[10px] font-black text-gray-500 uppercase tracking-tighter mb-2">Field Width ({block.width}/12)</label>
                                        <input
                                            type="range"
                                            min="3"
                                            max="12"
                                            step="1"
                                            value={block.width || 12}
                                            onChange={e => updateBlock(block.id, { width: parseInt(e.target.value) })}
                                            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-indigo-600"
                                        />
                                        <div className="flex justify-between text-[8px] text-gray-400 mt-1 font-bold">
                                            <span>QUARTER</span>
                                            <span>HALF</span>
                                            <span>FULL</span>
                                        </div>
                                    </div>

                                    <div className="pt-8 block border-t">
                                        <button
                                            onClick={() => removeBlock(block.id)}
                                            className="w-full py-3 text-xs font-bold text-red-400 hover:text-red-500 hover:bg-red-50 rounded-xl transition-all"
                                        >
                                            Delete Field
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="flex flex-col items-center justify-center h-full text-center opacity-30">
                            <div className="text-4xl mb-3">👈</div>
                            <p className="text-xs font-medium text-gray-400 italic">Select a field to configure its behavior.</p>
                        </div>
                    )}
                </aside>
            </div>

            <style jsx global>{`
        @keyframes slideInFromRight {
          from { transform: translateX(20px); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
        .animate-in {
          animation: slideInFromRight 0.4s cubic-bezier(0.16, 1, 0.3, 1);
        }
      `}</style>
        </main>
    );
}

export default function TemplateBuilder() {
    return (
        <Suspense fallback={
            <div className="min-h-screen flex items-center justify-center bg-gray-50">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
                    <p className="text-gray-500 font-medium">Initializing Builder...</p>
                </div>
            </div>
        }>
            <TemplateBuilderContent />
        </Suspense>
    );
}
