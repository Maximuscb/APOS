import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { api } from '@/lib/api';
import { useAuth } from './AuthContext';
import { loadState, saveState } from '@/lib/storage';

interface StoreInfo {
  id: number;
  name: string;
}

interface StoreContextValue {
  currentStoreId: number;
  currentStoreName: string;
  setStoreId: (id: number) => void;
  stores: StoreInfo[];
}

const StoreContext = createContext<StoreContextValue | null>(null);

export function StoreProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [stores, setStores] = useState<StoreInfo[]>([]);
  const [currentStoreId, setCurrentStoreIdState] = useState<number>(
    () => loadState<number>('storeId', 1)
  );

  useEffect(() => {
    if (!user) {
      setStores([]);
      return;
    }
    const boundStoreId = user.is_developer ? null : user.store_id;

    if (boundStoreId && currentStoreId !== boundStoreId) {
      setCurrentStoreIdState(boundStoreId);
      saveState('storeId', boundStoreId);
    }

    api.get<{ stores?: StoreInfo[] } | StoreInfo[]>('/api/stores')
      .then((data) => {
        const resolvedStores = Array.isArray(data) ? data : (data.stores ?? []);
        if (resolvedStores.length > 0) {
          setStores(resolvedStores);
          const hasCurrent = resolvedStores.some((s) => s.id === currentStoreId);
          if (!hasCurrent) {
            const nextStoreId = boundStoreId ?? resolvedStores[0].id;
            setCurrentStoreIdState(nextStoreId);
            saveState('storeId', nextStoreId);
          }
        }
      })
      .catch(() => {
        if (boundStoreId) {
          setStores([{ id: boundStoreId, name: `Store ${boundStoreId}` }]);
        }
      });
  }, [user, currentStoreId]);

  const setStoreId = (id: number) => {
    setCurrentStoreIdState(id);
    saveState('storeId', id);
  };

  const currentStoreName = stores.find((s) => s.id === currentStoreId)?.name ?? `Store ${currentStoreId}`;

  return (
    <StoreContext.Provider value={{ currentStoreId, currentStoreName, setStoreId, stores }}>
      {children}
    </StoreContext.Provider>
  );
}

export function useStore() {
  const ctx = useContext(StoreContext);
  if (!ctx) throw new Error('useStore must be used within StoreProvider');
  return ctx;
}
