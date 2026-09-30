import { useNavigate } from "react-router-dom";

import { Breadcrumbs } from "@/app/shell/Breadcrumbs";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useSession, useSignOut } from "@/features/auth/useAuth";
import { useAppUiStore } from "@/stores/appUiStore";

export function Topbar() {
  const openCommandPalette = useAppUiStore((state) => state.openCommandPalette);
  const session = useSession();
  const signOut = useSignOut();
  const navigate = useNavigate();

  const initials = (session.user?.displayName ?? "R")
    .slice(0, 2)
    .toUpperCase();

  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-border bg-surface px-6">
      <Breadcrumbs />
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={openCommandPalette}
          className="w-56 justify-between text-muted-foreground"
        >
          <span>Search</span>
          <kbd className="pointer-events-none rounded border border-border bg-muted px-1.5 font-mono text-micro">
            ⌘K
          </kbd>
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="rounded-full">
              <span className="flex size-6 items-center justify-center rounded-full bg-secondary text-micro font-medium">
                {initials}
              </span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>
              {session.user?.displayName ?? "Workspace"}
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuLabel className="text-micro font-normal text-muted-foreground">
              Roles: {session.user?.roles.join(", ") || "none"}
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => {
                signOut();
                navigate("/signin");
              }}
            >
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
