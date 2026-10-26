import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  Gauge,
  Users,
  Motorcycle,
  CalendarCheck,
  CurrencyInr,
  ChartLine,
  SignOut,
  Clock,
  CalendarBlank,
  MapPin,
} from "@phosphor-icons/react";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";

const NAV = [
  { to: "/dashboard", label: "Dashboard", Icon: Gauge },
  { to: "/schedule", label: "Schedule", Icon: CalendarBlank },
  { to: "/students", label: "Students", Icon: Users },
  { to: "/trainers", label: "Trainers", Icon: Motorcycle, managerOrAdmin: true },
  { to: "/attendance", label: "Attendance", Icon: CalendarCheck },
  { to: "/reports", label: "Reports", Icon: ChartLine, managerOrAdmin: true },
  { to: "/payments", label: "Payments", Icon: CurrencyInr, adminOnly: true },
];

const SETTINGS_NAV = [
  { to: "/slots", label: "Slots", Icon: Clock, managerOrAdmin: true },
];

export default function Sidebar({ isOpen, setIsOpen }) {
  const { user, logout, updateLocation } = useAuth();
  const navigate = useNavigate();

  const onLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-zinc-900/50 z-40 lg:hidden backdrop-blur-sm"
          onClick={() => setIsOpen(false)}
        />
      )}
      
      <aside
        data-testid="sidebar"
        className={`fixed inset-y-0 left-0 w-64 flex flex-col bg-zinc-50 border-r border-zinc-200 z-50 transition-transform duration-300 ease-in-out ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        } lg:translate-x-0`}
      >
        <div className="p-6 border-b border-zinc-200 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-zinc-900 flex items-center justify-center">
            <Motorcycle size={22} weight="bold" className="text-yellow-400" />
          </div>
          <div>
            <div className="font-heading font-black text-lg leading-none tracking-tighter">
              RIDEWELL
            </div>
            <div className="label-tag mt-1">Ops Console</div>
          </div>
        </div>
      </div>

      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        {NAV.filter((n) => {
          if (n.adminOnly) return user?.role === "admin";
          if (n.managerOrAdmin) return user?.role === "admin" || user?.role === "manager";
          return true;
        }).map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            data-testid={`nav-${label.toLowerCase()}`}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 text-sm font-semibold transition-colors ${
                isActive
                  ? "bg-zinc-900 text-white"
                  : "text-zinc-700 hover:bg-zinc-200"
              }`
            }
          >
            <Icon size={18} weight="bold" />
            <span>{label}</span>
          </NavLink>
        ))}

        {SETTINGS_NAV.filter((n) => {
          if (n.adminOnly) return user?.role === "admin";
          if (n.managerOrAdmin) return user?.role === "admin" || user?.role === "manager";
          return true;
        }).length > 0 && (
          <>
            <div className="label-tag px-3 py-2 pt-6">Settings</div>
            {SETTINGS_NAV.filter((n) => {
              if (n.adminOnly) return user?.role === "admin";
              if (n.managerOrAdmin) return user?.role === "admin" || user?.role === "manager";
              return true;
            }).map(({ to, label, Icon }) => (
              <NavLink
                key={to}
                to={to}
                data-testid={`nav-${label.toLowerCase().replace(/\s+/g, "-")}`}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 text-sm font-semibold transition-colors ${
                    isActive
                      ? "bg-zinc-900 text-white"
                      : "text-zinc-700 hover:bg-zinc-200"
                  }`
                }
              >
                <Icon size={18} weight="bold" />
                <span>{label}</span>
              </NavLink>
            ))}
          </>
        )}
      </nav>

      <div className="p-3 border-t border-zinc-200">
        <div className="px-3 py-2 mb-2">
          <div className="label-tag">Signed in as</div>
          <div className="text-sm font-semibold text-zinc-900 truncate">{user?.name}</div>
          <div className="text-xs text-zinc-500 truncate">{user?.email}</div>
          <div className="mt-1 flex items-center gap-1.5 flex-wrap">
            <span className="inline-block text-[10px] px-2 py-0.5 bg-yellow-400 text-zinc-900 font-bold uppercase tracking-wider">
              {user?.role}
            </span>
            <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 bg-blue-100 text-blue-900 font-bold uppercase tracking-wider">
              <MapPin size={10} weight="bold" /> {user?.location || "Khajaguda"}
            </span>
          </div>

          {(user?.role === "admin" || user?.role === "manager") && (
            <div className="mt-2.5 pt-2 border-t border-zinc-200">
              <label className="block text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-1">
                Change Branch
              </label>
              <select
                value={user?.location || "Khajaguda"}
                onChange={async (e) => {
                  const newLoc = e.target.value;
                  const res = await updateLocation(newLoc);
                  if (res.ok) {
                    toast.success(`Active branch changed to ${newLoc}`);
                  } else {
                    toast.error(res.error || "Failed to change branch");
                  }
                }}
                className="w-full text-xs font-bold uppercase tracking-wider bg-white border border-zinc-300 px-2 py-1.5 outline-none cursor-pointer hover:border-zinc-900 focus:border-zinc-900 transition-colors"
                data-testid="sidebar-branch-switcher"
              >
                <option value="Khajaguda">Khajaguda Branch</option>
                <option value="Madhapur">Madhapur Branch</option>
                <option value="Attapur">Attapur Branch</option>
              </select>
            </div>
          )}
        </div>
        <button
          onClick={onLogout}
          data-testid="logout-btn"
          className="w-full flex items-center justify-center gap-2 px-3 py-2.5 text-xs font-bold uppercase tracking-wider border border-zinc-300 hover:bg-zinc-900 hover:text-white hover:border-zinc-900 transition-colors"
        >
          <SignOut size={14} weight="bold" />
          Log out
        </button>
      </div>
    </aside>
    </>
  );
}
