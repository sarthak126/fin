import type { Metadata } from "next";

import { ArgentNorthPrototypeShell } from "@/components/argentnorth/prototype-shell";

export const metadata: Metadata = {
  title: "ArgentNorth Prototype 2",
  description:
    "Second static ArgentNorth prototype route for reviewing the institutional credit decision fabric shell.",
};

export default function Prototype2Page() {
  return <ArgentNorthPrototypeShell />;
}
