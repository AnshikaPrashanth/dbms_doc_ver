import React from "react";

export default function Footer() {
  return (
    <footer className="gov-footer">
      © {new Date().getFullYear()} GovVerify — Secure Document Services
    </footer>
  );
}
