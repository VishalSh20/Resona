import { http } from "./client";
import type { AuthUserDto, TokenResponseDto } from "@/types/api";
import { toAuthUserVM, type AuthUserVM } from "@/lib/mappers";

export interface SignInInput {
  email: string;
  password: string;
}

export interface SignUpInput {
  email: string;
  password: string;
  username?: string;
}

export interface AuthSession {
  accessToken: string;
  user: AuthUserVM;
}

function toSession(dto: TokenResponseDto): AuthSession {
  return { accessToken: dto.access_token, user: toAuthUserVM(dto.user) };
}

export const authApi = {
  register: (input: SignUpInput) =>
    http
      .post<TokenResponseDto>("/auth/register", {
        email: input.email,
        password: input.password,
        username: input.username ?? null,
      })
      .then(toSession),
  login: (input: SignInInput) =>
    http.post<TokenResponseDto>("/auth/login", input).then(toSession),
  me: () => http.get<AuthUserDto>("/auth/me").then(toAuthUserVM),
};
