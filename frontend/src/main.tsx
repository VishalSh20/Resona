import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "@fontsource-variable/inter-tight";
import "@fontsource-variable/geist-mono";
import "@fontsource/instrument-serif";
import "./index.css";

import { App } from "@/app/App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
