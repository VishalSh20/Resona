import { http } from "./client";
import type { MediaUrlDto } from "@/types/api";

export interface SignedMediaUrl {
  url: string;
  expiresInSeconds: number;
}

export const mediaApi = {
  getSignedUrl: (mediaId: string) =>
    http.get<MediaUrlDto>(`/media/${mediaId}/url`).then((dto) => ({
      url: dto.url,
      expiresInSeconds: dto.expires_in_seconds,
    })),
};
