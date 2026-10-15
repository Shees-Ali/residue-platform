import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { QueryProvider } from "./api/QueryProvider";
import { AuthProvider } from "./auth/AuthProvider";
import { ToastProvider } from "./components/ui/toast";
import "./index.css";
import "./styles/fasalloop.css";
import "./styles/auth.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ToastProvider>
      <QueryProvider>
        <BrowserRouter>
          <AuthProvider>
            <App />
          </AuthProvider>
        </BrowserRouter>
      </QueryProvider>
    </ToastProvider>
  </React.StrictMode>,
);
