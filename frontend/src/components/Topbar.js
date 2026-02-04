import React from "react";
import { NavLink } from "react-router-dom";

export default function Topbar({ user, onLogout }) {
  return (
    <header className="gov-topbar">
      <div className="gov-container">
        <div className="brand">GovVerify</div>

        <nav className="nav">
          <NavLink to="/">Home</NavLink>
          <NavLink to="/upload">Upload</NavLink>
          <NavLink to="/verify">Verify</NavLink>

          {user && <NavLink to="/dashboard">Dashboard</NavLink>}
          {user && user.role === "admin" && <NavLink to="/admin">Admin</NavLink>}

          {!user ? (
            <NavLink to="/login" className="btn-outline">
              Sign in
            </NavLink>
          ) : (
            <button className="btn-ghost" onClick={onLogout}>
              Sign out
            </button>
          )}
        </nav>
      </div>
    </header>
  );
}
