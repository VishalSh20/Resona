import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { FormField } from "@/components/forms/FormField";
import { ErrorState } from "@/components/domain/States";
import { PageHeader } from "@/components/domain/PageHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useCreateBenchmark } from "@/features/benchmarks/queries";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

const schema = z.object({
  benchmarkKey: z.string().min(1, "Key is required"),
  name: z.string().min(1, "Name is required"),
});

type FormValues = z.infer<typeof schema>;

export function BenchmarkCreatePage() {
  useDocumentTitle("New benchmark");
  const navigate = useNavigate();
  const createBenchmark = useCreateBenchmark();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { benchmarkKey: "", name: "" },
  });

  const onSubmit = handleSubmit(async (values) => {
    const benchmark = await createBenchmark.mutateAsync({
      benchmark_key: values.benchmarkKey,
      name: values.name,
    });
    navigate(`/app/benchmarks/${benchmark.id}/overview`);
  });

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <PageHeader
        title="New benchmark"
        description="A benchmark groups evaluator revisions into a reproducible suite."
      />
      <Card className="p-6">
        <form onSubmit={onSubmit} className="space-y-4">
          <FormField
            label="Name"
            htmlFor="name"
            required
            error={errors.name?.message}
          >
            <Input id="name" {...register("name")} placeholder="Customer Support" />
          </FormField>
          <FormField
            label="Key"
            htmlFor="benchmarkKey"
            required
            hint="Stable machine key, e.g. customer_support."
            error={errors.benchmarkKey?.message}
          >
            <Input
              id="benchmarkKey"
              {...register("benchmarkKey")}
              placeholder="customer_support"
              className="font-mono text-mono"
            />
          </FormField>

          {createBenchmark.isError && (
            <ErrorState
              error={createBenchmark.error}
              title="Could not create benchmark."
            />
          )}

          <div className="flex items-center justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => navigate("/app/benchmarks")}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={createBenchmark.isPending}>
              {createBenchmark.isPending ? "Creating…" : "Create benchmark"}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
