import { NavLink } from "react-router-dom";

import { Logo } from "@/components/brand/Logo";
import { primaryNav } from "@/lib/constants/navigation";
import { cn } from "@/lib/utils";

export function Sidebar() {
  return (
    <aside className="hidden w-56 shrink-0 border-r border-border bg-surface md:flex md:flex-col">
      <div className="flex h-14 shrink-0 items-center border-b border-border px-4">
        <Logo showTagline />
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        {primaryNav.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.end}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-2.5 rounded-md px-3 py-2 text-body-sm font-medium text-muted-foreground transition-colors hover:bg-surface-hover hover:text-foreground",
                isActive && "bg-surface-selected text-foreground",
              )
            }
          >
            <item.icon className="size-4" aria-hidden />
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-border p-3 text-micro text-muted-foreground">
        v0.1
      </div>
    </aside>
  );
}
