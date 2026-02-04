import React from "react";
import { Link } from "react-router-dom";

export default function Home() {
  return (
    <section className="text-center text-light">

      {/* HERO */}
      <div className="mb-5">
        <h1 className="fw-bold display-5">
          Secure Document Verification
        </h1>

        <p className="lead mt-3 text-light opacity-75">
          Government-grade platform for tamper-proof document verification
          using OCR, AI extraction, and cryptographic hashing.
        </p>

        <div className="d-flex justify-content-center gap-3 mt-4">
          <Link to="/upload" className="btn btn-primary btn-lg px-4">
            <i className="bi bi-upload me-2"></i>
            Upload Document
          </Link>

          <Link to="/verify" className="btn btn-outline-light btn-lg px-4">
            <i className="bi bi-shield-check me-2"></i>
            Verify Document
          </Link>
        </div>
      </div>

      {/* FEATURES */}
      <div className="row g-4 mb-5">
        <div className="col-md-4">
          <div className="card h-100">
            <div className="card-body text-center">
              <i className="bi bi-fingerprint display-5 text-primary"></i>
              <h5 className="mt-3">Cryptographic Hashing</h5>
              <p className="text-muted">
                Each document is fingerprinted using secure SHA-256 hashing
                to prevent tampering.
              </p>
            </div>
          </div>
        </div>

        <div className="col-md-4">
          <div className="card h-100">
            <div className="card-body text-center">
              <i className="bi bi-eye display-5 text-primary"></i>
              <h5 className="mt-3">OCR & AI Extraction</h5>
              <p className="text-muted">
                Text is extracted using OCR and analyzed for authenticity
                using intelligent validation.
              </p>
            </div>
          </div>
        </div>

        <div className="col-md-4">
          <div className="card h-100">
            <div className="card-body text-center">
              <i className="bi bi-journal-check display-5 text-primary"></i>
              <h5 className="mt-3">Audit Trail</h5>
              <p className="text-muted">
                All verification actions are logged to ensure transparency
                and traceability.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* HOW IT WORKS */}
      <div className="card mx-auto" style={{ maxWidth: "900px" }}>
        <div className="card-body">
          <h3 className="mb-4 text-center">How it works</h3>

          <div className="row text-start">
            <div className="col-md-4">
              <p>
                <i className="bi bi-1-circle-fill text-primary me-2"></i>
                Upload a document and generate a secure cryptographic hash.
              </p>
            </div>

            <div className="col-md-4">
              <p>
                <i className="bi bi-2-circle-fill text-primary me-2"></i>
                Metadata and hash are securely stored with a full audit log.
              </p>
            </div>

            <div className="col-md-4">
              <p>
                <i className="bi bi-3-circle-fill text-primary me-2"></i>
                Verify authenticity anytime using document or hash.
              </p>
            </div>
          </div>
        </div>
      </div>

    </section>
  );
}
