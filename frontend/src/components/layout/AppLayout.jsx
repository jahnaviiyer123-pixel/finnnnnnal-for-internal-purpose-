import React, { useState, useEffect } from "react";
import { Outlet, Navigate, useLocation } from "react-router-dom";
import Sidebar from "@/components/layout/Sidebar";
import { useAuth } from "@/context/AuthContext";
import { List } from "@phosphor-icons/react";

export default function AppLayout() {
  const { user, ready } = useAuth();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const location = useLocation();

  // Close sidebar on route change for mobile
  useEffect(() => {
    setIsSidebarOpen(false);
  }, [location.pathname]);
  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-50">
        <div className="label-tag animate-pulse">Loading…</div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;

  return (
    <div className="min-h-screen bg-zinc-50 flex flex-col lg:flex-row">
      <Sidebar isOpen={isSidebarOpen} setIsOpen={setIsSidebarOpen} />
      
      <div className="flex-1 lg:pl-64 flex flex-col min-h-screen min-w-0">
        {/* Mobile Header */}
        <header className="lg:hidden flex items-center justify-between p-4 bg-zinc-50 border-b border-zinc-200 sticky top-0 z-30">
          <div className="font-heading font-black text-lg tracking-tighter">RIDEWELL</div>
          <button 
            onClick={() => setIsSidebarOpen(true)}
            className="p-2 -mr-2 text-zinc-900 hover:bg-zinc-200 rounded-md transition-colors"
          >
            <List size={24} weight="bold" />
          </button>
        </header>

        <main className="flex-1 w-full max-w-full">
          <div className="max-w-7xl mx-auto p-4 md:p-8 lg:p-12">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
