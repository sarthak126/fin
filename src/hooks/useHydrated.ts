"use client";

import { useSyncExternalStore } from "react";

function subscribeToHydration() {
  return () => undefined;
}

export function useHydrated() {
  return useSyncExternalStore(subscribeToHydration, () => true, () => false);
}
