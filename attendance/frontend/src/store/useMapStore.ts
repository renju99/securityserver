import { create } from 'zustand';

interface MapState {
    searchQuery: string;
    setSearchQuery: (query: string) => void;

    selectedId: string | null;
    setSelectedId: (id: string | null) => void;

    mapCenter: { lat: number, lng: number };
    setMapCenter: (center: { lat: number, lng: number }) => void;

    zoom: number;
    setZoom: (zoom: number) => void;
}

export const useMapStore = create<MapState>((set) => ({
    searchQuery: '',
    setSearchQuery: (searchQuery) => set({ searchQuery }),

    selectedId: null,
    setSelectedId: (selectedId) => set({ selectedId }),

    mapCenter: { lat: 25.2048, lng: 55.2708 },
    setMapCenter: (mapCenter) => set({ mapCenter }),

    zoom: 11,
    setZoom: (zoom) => set({ zoom })
}));
