import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";
import "./company.css";
import "./events.css";
import "./workspace-design.css";
import "./accounts-design.css";
import "./knowledge-design.css";
import "./operations-design.css";
import "./input-interactions.css";
import "./incident-panel.css";

// Text fields match :focus-visible even after a click. Track Tab separately so
// pointer focus does not leave frames, while keyboard users retain an indicator.
document.addEventListener("pointerdown", () => {
  document.documentElement.dataset.inputMethod = "pointer";
}, true);
document.addEventListener("keydown", (event) => {
  if (event.key === "Tab") document.documentElement.dataset.inputMethod = "keyboard";
}, true);
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
