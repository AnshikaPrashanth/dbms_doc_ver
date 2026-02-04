import React, { useState } from "react";
import client from "../api/client";

export default function Upload({ user }) {
  const [file, setFile] = useState(null);
  const [docType, setDocType] = useState("aadhaar");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const submit = async () => {
    if (!file) return alert("Select a file");

    setLoading(true);
    setResult(null);

    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("doc_type", docType);

      const res = await client.post("/upload", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      setResult({
        success: true,
        data: res.data,
      });
    } catch (err) {
      if (err.response && err.response.status === 409) {
        setResult({
          success: false,
          message: err.response.data.error,
        });
      } else {
        alert(err.response?.data?.error || err.response?.data?.message || "Upload failed");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="gov-container">
      <div className="card">
        <h2>Upload Document</h2>
        <p className="muted">
          Accepted formats: PNG, JPG, JPEG, TIF, TIFF, BMP
        </p>

        {/* FILE DROP */}
        <label className="file-drop">
          <input
            type="file" accept=".png,.jpg,.jpeg,.tif,.tiff,.bmp"
            className="file-input-hidden"
            onChange={(e) => setFile(e.target.files[0])}
          />
          <div className="file-drop-inner">
            {file ? file.name : "Click or drag a file here"}
          </div>
        </label>

        {/* ACTION ROW */}
        <div className="form-row">
          <select
            className="input"
            value={docType}
            onChange={(e) => setDocType(e.target.value)}
          >
            <option value="aadhaar">Aadhaar</option>
            <option value="passport">Passport</option>
            <option value="certificate">Certificate</option>
            <option value="other">Other</option>
          </select>

          <button
            className="btn-primary"
            onClick={submit}
            disabled={loading}
          >
            {loading ? "Uploading..." : "Upload"}
          </button>
        </div>

        {/* RESULT */}
        {result && (
          <div
            className={`result-box ${
              result.success ? "" : "border-danger"
            }`}
          >
            {result.success ? (
              <>
                <h4 className="text-success">
                  <i className="bi bi-check-circle-fill"></i>{" "}
                  Upload Successful
                </h4>
                <pre>{JSON.stringify(result.data, null, 2)}</pre>
              </>
            ) : (
              <>
                <h4 className="text-warning">
                  <i className="bi bi-exclamation-triangle-fill"></i>{" "}
                  Upload Blocked
                </h4>
                <p>{result.message}</p>
              </>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
