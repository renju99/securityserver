import React, { useState, useEffect, useRef } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

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
    assignee: string; // User email or placeholder name
}

interface PdfFillerProps {
    fileUrl: string;
    fields: SignatureField[];
    formData: any;
    onFormDataChange: (key: string, value: string) => void;
    currentUser: any;
}

export default function PdfFiller({ fileUrl, fields, formData, onFormDataChange, currentUser }: PdfFillerProps) {
    const [numPages, setNumPages] = useState<number | null>(null);
    const [scale, setScale] = useState(1.2);
    const [containerWidth, setContainerWidth] = useState(800);
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const updateWidth = () => {
            if (containerRef.current) {
                const padding = window.innerWidth < 768 ? 20 : 64;
                const newWidth = containerRef.current.offsetWidth - padding;
                setContainerWidth(newWidth > 0 ? newWidth : 300);
            }
        };

        updateWidth();
        window.addEventListener('resize', updateWidth);
        return () => window.removeEventListener('resize', updateWidth);
    }, []);

    const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
        setNumPages(numPages);
    };

    return (
        <div className="bg-white border rounded-lg shadow-sm overflow-hidden flex flex-col">
            <div className="bg-gray-50 border-b px-4 py-2 flex justify-between items-center">
                <span className="text-xs font-bold text-gray-500 uppercase tracking-widest">Document View</span>
                <div className="flex items-center space-x-2 bg-white rounded-md border px-2 py-1 shadow-sm">
                    <button onClick={() => setScale(Math.max(0.5, scale - 0.1))} className="text-gray-500 font-bold hover:text-indigo-600 px-2">-</button>
                    <span className="text-xs font-bold w-10 text-center">{Math.round(scale * 100)}%</span>
                    <button onClick={() => setScale(Math.min(2.5, scale + 0.1))} className="text-gray-500 font-bold hover:text-indigo-600 px-2">+</button>
                </div>
            </div>
            <div ref={containerRef} className="flex-1 overflow-auto bg-gray-200 p-4 md:p-8 flex justify-center min-h-[600px] h-[75vh]">
                <Document
                    file={fileUrl}
                    onLoadSuccess={onDocumentLoadSuccess}
                    loading={<div className="p-10">Loading PDF Form...</div>}
                    error={<div className="p-10 text-red-500">Failed to load PDF Form.</div>}
                >
                    {Array.from(new Array(numPages || 0), (el, index) => (
                        <div key={`page_${index + 1}`} className="relative mb-6 shadow-xl">
                            <Page
                                pageNumber={index + 1}
                                width={containerWidth * scale}
                                renderAnnotationLayer={false}
                                renderTextLayer={false}
                            />
                            {fields.filter(f => f.page === index + 1).map(f => {
                                const isCurrentUser = currentUser?.email === f.assignee || currentUser?.role === f.assignee;
                                const isGreyedOut = f.type === 'signature' || f.type === 'initial' || f.type === 'name';

                                return (
                                    <div
                                        key={f.id}
                                        className={`absolute flex items-center justify-center overflow-hidden transition-all
                                        ${isGreyedOut ? 'bg-gray-200/50 border border-gray-400' : 'bg-yellow-100/30 border-2 border-yellow-400 hover:bg-yellow-100/50'}
                                    `}
                                        style={{
                                            left: `${f.x}%`,
                                            top: `${f.y}%`,
                                            width: `${f.width}%`,
                                            height: `${f.height}%`,
                                            zIndex: 10
                                        }}
                                        title={`Type: ${f.type}, Assignee: ${f.assignee}`}
                                    >
                                        {isGreyedOut ? (
                                            <span className="text-gray-500 font-black text-[10px] md:text-sm uppercase tracking-wider text-center px-1">
                                                {f.type}
                                                <br />
                                                <span className="text-[8px] md:text-[10px] opacity-70">({f.assignee})</span>
                                            </span>
                                        ) : (
                                            <input
                                                type={f.type === 'date' ? 'date' : 'text'}
                                                className="w-full h-full bg-transparent outline-none px-2 text-xs md:text-sm font-medium text-blue-900 border-none placeholder-blue-300"
                                                placeholder={f.assignee || 'Enter text...'}
                                                defaultValue={formData[f.assignee || f.id] || ''}
                                                onBlur={(e) => onFormDataChange(f.assignee || f.id, e.target.value)}
                                            />
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    ))}
                </Document>
            </div>
        </div>
    );
}
