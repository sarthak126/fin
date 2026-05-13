import { AuthBootstrap } from "@/components/AuthBootstrap";

export default function ReportsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AuthBootstrap>{children}</AuthBootstrap>;
}
