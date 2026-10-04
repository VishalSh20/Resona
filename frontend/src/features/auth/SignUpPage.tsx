import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { Logo } from "@/components/brand/Logo";
import { ErrorState } from "@/components/domain/States";
import { FormField } from "@/components/forms/FormField";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useSignUp } from "@/features/auth/useAuth";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { BRAND } from "@/lib/constants/brand";

const schema = z
  .object({
    email: z.string().min(1, "Email is required"),
    username: z.string().optional(),
    password: z.string().min(8, "Use at least 8 characters"),
    confirmPassword: z.string().min(1, "Confirm your password"),
  })
  .refine((values) => values.password === values.confirmPassword, {
    path: ["confirmPassword"],
    message: "Passwords do not match",
  });

type FormValues = z.infer<typeof schema>;

export function SignUpPage() {
  useDocumentTitle("Create account");
  const navigate = useNavigate();
  const signUp = useSignUp();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      email: "",
      username: "",
      password: "",
      confirmPassword: "",
    },
  });

  const onSubmit = handleSubmit(async (values) => {
    await signUp.mutateAsync({
      email: values.email,
      password: values.password,
      username: values.username || undefined,
    });
    navigate("/app", { replace: true });
  });

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-6 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-1 text-center">
          <Logo />
          <p className="text-body-sm text-muted-foreground">
            {BRAND.tagline}
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
              label="Username"
              htmlFor="username"
              hint="Optional."
              error={errors.username?.message}
            >
              <Input
                id="username"
                autoComplete="username"
                {...register("username")}
              />
            </FormField>
            <FormField
              label="Password"
              htmlFor="password"
              required
              hint="At least 8 characters."
              error={errors.password?.message}
            >
              <Input
                id="password"
                type="password"
                autoComplete="new-password"
                {...register("password")}
              />
            </FormField>
            <FormField
              label="Confirm password"
              htmlFor="confirmPassword"
              required
              error={errors.confirmPassword?.message}
            >
              <Input
                id="confirmPassword"
                type="password"
                autoComplete="new-password"
                {...register("confirmPassword")}
              />
            </FormField>

            {signUp.isError && (
              <ErrorState error={signUp.error} title="Could not create account." />
            )}

            <Button
              type="submit"
              className="w-full"
              disabled={signUp.isPending}
            >
              {signUp.isPending ? "Creating account…" : "Create account"}
            </Button>
          </form>
        </Card>
        <p className="mt-4 text-center text-body-sm text-muted-foreground">
          Already have an account?{" "}
          <Link to="/signin" className="font-medium text-foreground underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
