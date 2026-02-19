'use client';

import dynamic from 'next/dynamic';

const PdfAnnotator = dynamic(() => import('@/components/PdfAnnotator'), {
    ssr: false,
    loading: () => <p className="p-10 text-center font-bold">Loading PDF Editor...</p>,
});

export default function Page() {
    return <PdfAnnotator />;
}
