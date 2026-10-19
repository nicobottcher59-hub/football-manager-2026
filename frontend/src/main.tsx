import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";

const mount = document.getElementById("root");
if (!mount) throw new Error("Missing #root element");

ReactDOM.createRoot(mount).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
