import React, { useState, useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Topbar from "./Topbar";
import client from "../api/client";
import Footer from "./Footer";

import Home from "../pages/Home";
import Login from "../pages/Login";
import Register from "../pages/Register";
import Upload from "../pages/Upload";
import Dashboard from "../pages/Dashboard";
import Verify from "../pages/Verify";
import AdminPanel from "../pages/AdminPanel";
import NotFound from "../pages/NotFound";

export default function AppShell() {
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("dv_user"));
    } catch {
      return null;
    }
  });

  const handleLogout = async () => {
    try {
      await client.post("/logout");
    } catch {
      // ignore
    }
    localStorage.removeItem("dv_user");
    setUser(null);
  };


  return (
    <div className="app-shell">
      <Topbar user={user} onLogout={handleLogout} />

      <main className="app-content">
        <div className="page">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/login" element={<Login onLogin={setUser} />} />
            <Route path="/register" element={<Register onRegister={setUser} />} />

            <Route
              path="/upload"
              element={user ? <Upload user={user} /> : <Navigate to="/login" />}
            />

            <Route
              path="/dashboard"
              element={user ? <Dashboard user={user} /> : <Navigate to="/login" />}
            />

            <Route
              path="/verify"
              element={user ? <Verify /> : <Navigate to="/login" />}
            />

            <Route
              path="/admin"
              element={
                user && user.role === "admin" ? (
                  <AdminPanel user={user} />
                ) : (
                  <Navigate to="/login" />
                )
              }
            />

            <Route path="*" element={<NotFound />} />
          </Routes>
        </div>
      </main>

      <Footer />
    </div>
  );
}
