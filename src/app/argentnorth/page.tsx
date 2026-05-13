import type { Metadata } from "next";

import { ArgentNorthOS } from "@/components/argentnorth/argentnorth-os";

export const metadata: Metadata = {
  title: "ArgentNorth OS",
  description:
    "Institutional credit decision fabric for AI-powered underwriting, risk operations, governance, and financial intelligence.",
};

export default function ArgentNorthPage() {
  return <ArgentNorthOS />;
}
