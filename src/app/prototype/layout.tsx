import { PrototypePageFade } from "@/components/prototype/PrototypePageFade";
import { PrototypeSidebar } from "@/components/prototype/PrototypeSidebar";
import { PrototypeTopbar } from "@/components/prototype/PrototypeTopbar";
import { SidebarProvider } from "@/components/ui/sidebar";

export default function PrototypeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full bg-background font-sans text-foreground">
        <PrototypeSidebar />

        <div className="flex flex-1 flex-col">
          <PrototypeTopbar />

          <main className="flex-1 overflow-y-auto">
            <div className="px-5 py-8 md:px-10 lg:px-14">
              <div className="mx-auto max-w-[1440px]">
                <PrototypePageFade>{children}</PrototypePageFade>
              </div>
            </div>
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
}
