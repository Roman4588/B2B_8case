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
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
