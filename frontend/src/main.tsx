import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { applyInitialTheme } from "./state/Theme";
import "./styles/global.css";

// پوسته پیش از اولین رندر اعمال می‌شود تا چشمک روشن/تیره نداشته باشیم
applyInitialTheme();

const root = document.getElementById("root");
if (!root) throw new Error("root missing");
createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
