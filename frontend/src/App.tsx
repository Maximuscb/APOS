// Overview: App routing between Register Mode and Operations Suite.

import { useEffect, useState } from "react";
import { RegisterMode } from "./RegisterMode";
import { OperationsSuite } from "./OperationsSuite";
import { appConfig } from "./lib/config";

export default function App() {
  const [mode, setMode] = useState<"register" | "operations">(() => {
    return window.location.hash === "#register-mode" ? "register" : "operations";
  });

  useEffect(() => {
    document.title = appConfig.appName;
    const iconHref = appConfig.brand.iconHref;
    if (iconHref) {
      const link = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
      if (link) {
        link.href = iconHref;
      }
    }
    const handleHashChange = () => {
      if (window.location.hash === "#register-mode") {
        setMode("register");
      } else {
        setMode("operations");
      }
    };
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  if (mode === "register") {
    return (
      <RegisterMode
        onExit={() => {
          window.location.hash = "#overview";
          setMode("operations");
        }}
      />
    );
  }

  return (
    <OperationsSuite
      onEnterRegisterMode={() => {
        window.location.hash = "#register-mode";
        setMode("register");
      }}
    />
  );
}
