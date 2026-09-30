import type { ReactNode } from "react";

import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

interface FormFieldProps {
  label: string;
  htmlFor?: string;
  hint?: string;
  error?: string;
  required?: boolean;
  children: ReactNode;
  className?: string;
}

export function FormField({
  label,
  htmlFor,
  hint,
  error,
  required,
  children,
  className,
}: FormFieldProps) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <Label htmlFor={htmlFor}>
        {label}
        {required && <span className="text-red-600">*</span>}
      </Label>
      {children}
      {error ? (
        <p className="text-micro text-red-600">{error}</p>
      ) : hint ? (
        <p className="text-micro text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}
