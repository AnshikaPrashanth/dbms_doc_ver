import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import client from "../api/client";

export default function Register({ onRegister }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const navigate = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      await client.post("/register", {
        name,
        email,
        password,
      });

      // Auto-login after successful registration
      const loginRes = await client.post("/login", {
        email,
        password,
      });

      const { user } = loginRes.data;
      localStorage.setItem("dv_user", JSON.stringify(user));
      onRegister(user);

      navigate("/dashboard");
    } catch (err) {
      alert(err.response?.data?.error || "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section>
      <div className="card small">
        <h2>Create account</h2>

        <form onSubmit={submit} className="form">
          <input
            className="input"
            placeholder="Full name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />

          <input
            className="input"
            type="email"
            placeholder="Email address"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />

          <input
            className="input"
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />

          <div className="form-row">
            <button className="btn-primary" disabled={loading}>
              {loading ? "Creating..." : "Register"}
            </button>

            <Link to="/login" className="btn-secondary">
              Already have an account?
            </Link>
          </div>
        </form>
      </div>
    </section>
  );
}
