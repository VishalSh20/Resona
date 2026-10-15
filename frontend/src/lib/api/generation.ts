import { http } from "./client";
import type {
  SimulationPreferencesRequestDto,
  SimulationPreferencesResponseDto,
} from "@/types/api";

export const generationApi = {
  suggestPreferences: (input: SimulationPreferencesRequestDto) =>
    http.post<SimulationPreferencesResponseDto>(
      "/generation/simulation-preferences",
      input,
    ),
};
