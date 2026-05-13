import type { Metadata } from "next";

import { ArgentNorthPrototypeShell } from "@/components/argentnorth/prototype-shell";

export const metadata: Metadata = {
  title: "ArgentNorth Fresh UI Prototype",
  description:
    "Static full-shell ArgentNorth prototype for institutional AI credit intelligence workflows.",
};

export default function PrototypePage() {
  return <ArgentNorthPrototypeShell />;
}
