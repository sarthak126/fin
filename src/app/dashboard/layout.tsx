import { AppSidebar } from "@/components/app-sidebar";
import { SidebarProvider } from "@/components/ui/sidebar";
import { Topbar } from "@/components/Topbar";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full bg-background font-sans text-foreground">
        <AppSidebar />

        <div className="flex flex-1 flex-col">
          <Topbar />

          <main className="flex-1 overflow-y-auto">
            <div className="px-5 py-8 md:px-10 lg:px-14">
              <div className="mx-auto max-w-[1440px]">
                {children}
              </div>
            </div>
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
}
