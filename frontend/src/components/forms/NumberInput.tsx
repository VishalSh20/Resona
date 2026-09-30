import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface NumberInputProps {
  value: number | undefined;
  onChange: (value: number | undefined) => void;
  id?: string;
  placeholder?: string;
  step?: number;
  min?: number;
  max?: number;
  className?: string;
}

export function NumberInput({
  value,
  onChange,
  id,
  placeholder,
  step,
  min,
  max,
  className,
}: NumberInputProps) {
  return (
    <Input
      id={id}
      type="number"
      step={step}
      min={min}
      max={max}
      value={value ?? ""}
      placeholder={placeholder}
      className={cn("tabular-nums", className)}
      onChange={(event) => {
        const text = event.target.value;
        onChange(text === "" ? undefined : Number(text));
      }}
    />
  );
}
