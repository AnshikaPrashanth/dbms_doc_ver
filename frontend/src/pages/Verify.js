import React, { useState } from "react";
import client from "../api/client";

export default function Verify() {
  const [hash, setHash] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const submit = async () => {
    if (!hash.trim()) {
      alert("Please enter a document hash");
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      const res = await client.get(
        `/verify/${hash.trim()}`
      );
      setResult(res.data);
    } catch (err) {
      alert(err.response?.data?.message || "Verification failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section>
      <div className="card">
        <h2>Verify Document</h2>
        <p className="muted">
          Enter the SHA-256 document hash to verify authenticity.
        </p>

        <input
          className="input"
          placeholder="Enter document hash"
          value={hash}
          onChange={(e) => setHash(e.target.value)}
        />

        <div className="form-row">
          <button className="btn-primary" onClick={submit} disabled={loading}>
            {loading ? "Verifying..." : "Verify"}
          </button>
        </div>

        {result && (
          <div className="result-box success">
            <h4>Verification Result</h4>
            <pre>{JSON.stringify(result, null, 2)}</pre>
          </div>
        )}
      </div>
    </section>
  );
}
