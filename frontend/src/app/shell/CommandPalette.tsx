import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Search } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { primaryNav } from "@/lib/constants/navigation";
import { useAppUiStore } from "@/stores/appUiStore";

export function CommandPalette() {
  const open = useAppUiStore((state) => state.commandPaletteOpen);
  const close = useAppUiStore((state) => state.closeCommandPalette);
  const navigate = useNavigate();

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        useAppUiStore.getState().openCommandPalette();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) close();
      }}
    >
      <DialogContent className="top-[15%] translate-y-0 max-w-md sm:max-w-md p-0 gap-0">
        <DialogHeader className="sr-only">
          <DialogTitle>Command palette</DialogTitle>
        </DialogHeader>
        <div className="flex items-center gap-2 border-b border-border px-3">
          <Search
            className="size-4 shrink-0 text-muted-foreground"
            aria-hidden
          />
          <Input
            className="border-0 shadow-none focus-visible:ring-0"
            placeholder="Search simulations, benchmarks, agents…"
            autoFocus
          />
        </div>
        <div className="p-2">
          {primaryNav.map((item) => (
            <button
              key={item.path}
              type="button"
              onClick={() => {
                close();
                navigate(item.path);
              }}
              className="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-body-sm text-foreground transition-colors hover:bg-surface-hover"
            >
              <item.icon className="size-4 text-muted-foreground" aria-hidden />
              {item.label}
            </button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
