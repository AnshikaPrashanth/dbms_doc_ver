import React, { useState, useEffect } from "react";
import client from "../api/client";

export default function AdminPanel({ user }) {
  const [pending, setPending] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchPending();
  }, []);

  const fetchPending = async () => {
    try {
      const res = await client.get("/admin/pending");
      setPending(res.data.pending_documents || []);
    } catch (err) {
      console.error(err);
    }
  };

  const handleAction = async (doc_id, status) => {
    if (!window.confirm(`Are you sure you want to ${status} this document?`)) {
      return;
    }

    setLoading(true);
    try {
      await client.post(`/admin/verify/${doc_id}`, {
        status,
        remarks: status === "verified" ? "Approved" : "Rejected",
      });

      fetchPending();
    } catch (err) {
      alert("Action failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section>
      <div className="card">
        <h2>Admin — Pending Documents</h2>

        {pending.length === 0 ? (
          <p className="muted">No pending documents</p>
        ) : (
          <table className="doc-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Name</th>
                <th>User</th>
                <th>Uploaded</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {pending.map((p) => (
                <tr key={p.doc_id}>
                  <td>{p.doc_id}</td>
                  <td>{p.doc_name}</td>
                  <td>{p.user_id}</td>
                  <td>{new Date(p.upload_date).toLocaleString()}</td>
                  <td>
                    <button
                      className="btn-primary small"
                      onClick={() => handleAction(p.doc_id, "verified")}
                      disabled={loading}
                    >
                      Approve
                    </button>{" "}
                    <button
                      className="btn-secondary small"
                      onClick={() => handleAction(p.doc_id, "rejected")}
                      disabled={loading}
                    >
                      Reject
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
