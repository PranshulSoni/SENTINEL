import { create } from 'zustand';

export interface UndoAction {
  id: string;
  label: string;
  expiresAt: number;
  onUndo: () => Promise<void> | void;
  onCommit: () => void;
}

interface UIState {
  focusMode: 'normal' | 'incident';
  focusStack: string[]; // List of incident IDs
  activeFocusId: string | null;
  pendingUndoActions: UndoAction[];
  
  setFocusMode: (mode: 'normal' | 'incident') => void;
  pushFocusStack: (incidentId: string) => void;
  popFocusStack: (incidentId: string) => void;
  setActiveFocus: (incidentId: string | null) => void;
  
  addUndoAction: (action: Omit<UndoAction, 'expiresAt'>, timeout?: number) => void;
  removeUndoAction: (id: string) => void;
  commitUndoAction: (id: string) => void;
  triggerUndo: (id: string) => Promise<void>;
}

export const useUIStore = create<UIState>((set, get) => ({
  focusMode: 'normal',
  focusStack: [],
  activeFocusId: null,
  pendingUndoActions: [],

  setFocusMode: (focusMode) => set({ focusMode }),

  pushFocusStack: (incidentId) => set((state) => {
    if (state.focusStack.includes(incidentId)) {
      return { activeFocusId: incidentId };
    }
    const newStack = [incidentId, ...state.focusStack].slice(0, 3); // Max 3
    return { 
      focusStack: newStack, 
      activeFocusId: incidentId,
      focusMode: 'incident'
    };
  }),

  popFocusStack: (incidentId) => set((state) => {
    const newStack = state.focusStack.filter(id => id !== incidentId);
    const newActive = state.activeFocusId === incidentId 
      ? (newStack[0] || null) 
      : state.activeFocusId;
    return { 
      focusStack: newStack, 
      activeFocusId: newActive,
      focusMode: newStack.length > 0 ? 'incident' : 'normal'
    };
  }),

  setActiveFocus: (activeFocusId) => set({ activeFocusId }),

  addUndoAction: (action, timeout = 7000) => {
    const expiresAt = Date.now() + timeout;
    const newAction = { ...action, expiresAt };
    
    set((state) => ({
      pendingUndoActions: [...state.pendingUndoActions, newAction]
    }));

    setTimeout(() => {
      const currentActions = get().pendingUndoActions;
      if (currentActions.some(a => a.id === action.id)) {
        get().commitUndoAction(action.id);
      }
    }, timeout);
  },

  removeUndoAction: (id) => set((state) => ({
    pendingUndoActions: state.pendingUndoActions.filter(a => a.id !== id)
  })),

  commitUndoAction: (id) => {
    const action = get().pendingUndoActions.find(a => a.id === id);
    if (action) {
      action.onCommit();
      get().removeUndoAction(id);
    }
  },

  triggerUndo: async (id) => {
    const action = get().pendingUndoActions.find(a => a.id === id);
    if (action) {
      await action.onUndo();
      get().removeUndoAction(id);
    }
  }
}));

// Priority logic helper
export function deriveAlertPriority(incident: any): 'P0' | 'P1' | 'P2' | 'P3' {
  if (incident.severity === 'critical' && !incident.assigned_operator) return 'P0';
  if (incident.severity === 'critical') return 'P1';
  if (incident.severity === 'major') return 'P2';
  return 'P3';
}
