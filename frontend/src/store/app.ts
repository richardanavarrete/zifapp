import { create } from "zustand"
import { persist } from "zustand/middleware"
import type { Dataset, OrderTargets, OrderConstraints } from "@/types/api"

interface AppState {
  // Active dataset
  activeDatasetId: string | null
  activeDataset: Dataset | null
  setActiveDataset: (dataset: Dataset | null) => void

  // Theme
  theme: "light" | "dark" | "system"
  setTheme: (theme: "light" | "dark" | "system") => void

  // Order settings (persisted)
  orderTargets: OrderTargets
  orderConstraints: OrderConstraints
  setOrderTargets: (targets: Partial<OrderTargets>) => void
  setOrderConstraints: (constraints: Partial<OrderConstraints>) => void

  // UI state
  sidebarOpen: boolean
  setSidebarOpen: (open: boolean) => void
}

const defaultTargets: OrderTargets = {
  default_weeks: 2,
  by_category: {},
  by_item: {},
  exclude_items: [],
}

const defaultConstraints: OrderConstraints = {
  max_spend: undefined,
  max_items: undefined,
  vendor_minimums: {},
  vendor_maximums: {},
  low_stock_weeks: 1,
  overstock_weeks: 6,
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      // Active dataset
      activeDatasetId: null,
      activeDataset: null,
      setActiveDataset: (dataset) =>
        set({
          activeDataset: dataset,
          activeDatasetId: dataset?.dataset_id ?? null,
        }),

      // Theme
      theme: "system",
      setTheme: (theme) => set({ theme }),

      // Order settings
      orderTargets: defaultTargets,
      orderConstraints: defaultConstraints,
      setOrderTargets: (targets) =>
        set((state) => ({
          orderTargets: { ...state.orderTargets, ...targets },
        })),
      setOrderConstraints: (constraints) =>
        set((state) => ({
          orderConstraints: { ...state.orderConstraints, ...constraints },
        })),

      // UI state
      sidebarOpen: true,
      setSidebarOpen: (open) => set({ sidebarOpen: open }),
    }),
    {
      name: "zif-app-storage",
      partialize: (state) => ({
        activeDatasetId: state.activeDatasetId,
        theme: state.theme,
        orderTargets: state.orderTargets,
        orderConstraints: state.orderConstraints,
      }),
    }
  )
)
