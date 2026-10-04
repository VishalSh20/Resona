import { Link, useLocation, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { Logo } from "@/components/brand/Logo";
import { ErrorState } from "@/components/domain/States";
import { FormField } from "@/components/forms/FormField";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useSignIn } from "@/features/auth/useAuth";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { BRAND } from "@/lib/constants/brand";

const schema = z.object({
  email: z.string().min(1, "Email is required"),
  password: z.string().min(1, "Password is required"),
});

type FormValues = z.infer<typeof schema>;

export function SignInPage() {
  useDocumentTitle("Sign in");
  const navigate = useNavigate();
  const location = useLocation();
  const signIn = useSignIn();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  });

  const redirectTo =
    (location.state as { from?: string } | null)?.from ?? "/app";

  const onSubmit = handleSubmit(async (values) => {
    await signIn.mutateAsync(values);
    navigate(redirectTo, { replace: true });
  });

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-6 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-1 text-center">
          <Logo />
          <p className="text-body-sm text-muted-foreground">
            {BRAND.positioning}
          </p>
        </div>
        <Card className="p-6">
          <form onSubmit={onSubmit} className="space-y-4">
            <FormField
              label="Email"
              htmlFor="email"
              required
              error={errors.email?.message}
            >
              <Input
                id="email"
                type="email"
                autoComplete="email"
                {...register("email")}
                placeholder="operator@example.com"
              />
            </FormField>
            <FormField
              label="Password"
              htmlFor="password"
              required
              error={errors.password?.message}
            >
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                {...register("password")}
              />
            </FormField>

            {signIn.isError && (
              <ErrorState
                error={signIn.error}
                title="Could not sign in."
              />
            )}

            <Button
              type="submit"
              className="w-full"
              disabled={signIn.isPending}
            >
              {signIn.isPending ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </Card>
        <p className="mt-4 text-center text-body-sm text-muted-foreground">
          No account?{" "}
          <Link to="/signup" className="font-medium text-foreground underline">
            Create one
          </Link>
        </p>
      </div>
    </div>
  );
}
