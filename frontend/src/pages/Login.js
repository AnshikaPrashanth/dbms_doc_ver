import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import client from "../api/client";

export default function Login({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const navigate = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    if (!email.trim() || !password.trim()) {
      alert("Enter email and password");
      return;
    }

    setLoading(true);

    try {
      const res = await client.post("/login", {
        email,
        password,
      });

      const { user } = res.data;
      localStorage.setItem("dv_user", JSON.stringify(user));
      onLogin(user);

      navigate("/dashboard");
    } catch (err) {
      alert(err.response?.data?.error || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="container my-5">
      <div className="row justify-content-center">
        <div className="col-md-5">
          <div className="card p-4 shadow-sm">
            <h2 className="mb-3 text-center">Sign in</h2>

            <form onSubmit={submit}>
              <input
                className="form-control mb-3"
                type="email"
                placeholder="Email address"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />

              <input
                className="form-control mb-3"
                type="password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />

              <div className="d-flex gap-2">
                <button
                  type="submit"
                  className="btn btn-primary w-100"
                  disabled={loading}
                >
                  {loading ? "Signing in..." : "Sign in"}
                </button>

                <Link
                  to="/register"
                  className="btn btn-outline-secondary w-100"
                >
                  Register
                </Link>
              </div>
            </form>
          </div>
        </div>
      </div>
    </section>
  );
}
