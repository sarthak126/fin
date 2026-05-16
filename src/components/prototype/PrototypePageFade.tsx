"use client";

import { motion } from "framer-motion";
import { usePathname } from "next/navigation";

const EASE_OUT: [number, number, number, number] = [0.16, 1, 0.3, 1];

export function PrototypePageFade({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <motion.div
      key={pathname}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: EASE_OUT }}
    >
      {children}
    </motion.div>
  );
}
