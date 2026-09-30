import { Outlet } from "react-router-dom";

import { CommandPalette } from "@/app/shell/CommandPalette";
import { Sidebar } from "@/app/shell/Sidebar";
import { Topbar } from "@/app/shell/Topbar";

export function AppShell() {
  return (
    <div className="flex min-h-screen bg-canvas text-foreground">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="flex-1 px-8 py-6">
          <Outlet />
        </main>
      </div>
      <CommandPalette />
    </div>
  );
}
