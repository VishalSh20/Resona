import { useState } from "react";
import { Link } from "react-router-dom";
import { Menu, X } from "lucide-react";

import { Logo } from "@/components/brand/Logo";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { LANDING_COPY } from "@/features/landing/copy";

const { nav } = LANDING_COPY;

function Wordmark() {
  return (
    <a
      href="#top"
      className="inline-flex items-center text-foreground"
      aria-label="Resona home"
    >
      <Logo />
    </a>
  );
}

export function LandingNav() {
  const [open, setOpen] = useState(false);

  return (
    <header className="relative z-20">
      <div className="flex h-16 items-center justify-between px-6 md:px-10">
        <Wordmark />

        <nav
          aria-label="Primary"
          className="hidden items-center gap-8 md:flex"
        >
          {nav.links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-body-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="hidden items-center gap-5 md:flex">
          <Link
            to="/signin"
            className="text-body-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            {nav.signIn}
          </Link>
          <Button size="sm" asChild>
            <Link to="/signup">{nav.start}</Link>
          </Button>
        </div>

        <button
          type="button"
          className="inline-flex size-9 items-center justify-center rounded-md text-foreground md:hidden"
          aria-expanded={open}
          aria-controls="landing-mobile-menu"
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? <X className="size-5" /> : <Menu className="size-5" />}
        </button>
      </div>

      <div
        id="landing-mobile-menu"
        className={cn(
          "border-b border-border bg-white/95 px-6 backdrop-blur md:hidden",
          open ? "block" : "hidden",
        )}
      >
        <nav aria-label="Mobile" className="flex flex-col gap-1 py-4">
          {nav.links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              onClick={() => setOpen(false)}
              className="rounded-md px-2 py-2 text-body-sm text-muted-foreground transition-colors hover:bg-surface-hover hover:text-foreground"
            >
              {link.label}
            </a>
          ))}
          <Link
            to="/signin"
            onClick={() => setOpen(false)}
            className="rounded-md px-2 py-2 text-body-sm text-muted-foreground transition-colors hover:bg-surface-hover hover:text-foreground"
          >
            {nav.signIn}
          </Link>
          <Button size="sm" asChild className="mt-2">
            <Link to="/signup" onClick={() => setOpen(false)}>
              {nav.start}
            </Link>
          </Button>
        </nav>
      </div>
    </header>
  );
}
