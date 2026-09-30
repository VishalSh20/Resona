import { Input } from "@/components/ui/input";

interface StringListInputProps {
  value: string[];
  onChange: (value: string[]) => void;
  placeholder?: string;
  id?: string;
}

export function StringListInput({
  value,
  onChange,
  placeholder = "comma-separated values",
  id,
}: StringListInputProps) {
  return (
    <Input
      id={id}
      value={value.join(", ")}
      placeholder={placeholder}
      onChange={(event) => {
        const items = event.target.value
          .split(",")
          .map((item) => item.trim())
          .filter((item) => item.length > 0);
        onChange(items);
      }}
    />
  );
}
