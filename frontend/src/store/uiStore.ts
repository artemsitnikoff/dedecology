import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UiState {
  /** Развёрнут ли сайдбар (зарезервировано под будущий collapse). */
  sidebarOpen: boolean;
  setSidebarOpen: (v: boolean) => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      sidebarOpen: true,
      setSidebarOpen: (v) => set({ sidebarOpen: v }),
    }),
    { name: 'dedecolog-ui' }
  )
);
