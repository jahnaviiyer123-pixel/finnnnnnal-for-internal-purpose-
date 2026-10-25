import React, { useEffect, useState, useCallback, useMemo } from "react";
import { Link } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import {
  ChartLine,
  CalendarBlank,
  Users,
  Motorcycle,
  CurrencyInr,
  CheckCircle,
  XCircle,
  CaretLeft,
  CaretRight,
  Clock,
  ArrowClockwise,
  MapPin,
  Sparkle,
} from "@phosphor-icons/react";
import { toast } from "sonner";

export default function Reports() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const isManager = user?.role === "manager";
  const isManagerOrAdmin = isAdmin || isManager;

  const [period, setPeriod] = useState("weekly"); // "weekly" | "monthly" | "daily"
  const [locations, setLocations] = useState(["Khajaguda", "Manikonda", "Kondapur"]);
  const [selectedLocation, setSelectedLocation] = useState(isAdmin ? "" : (user?.location || "Khajaguda"));

  // Weekly date state (Monday to Sunday)
  const [weekOffset, setWeekOffset] = useState(0); // 0 = this week, -1 = last week, etc.

  // Monthly date state
  const [monthOffset, setMonthOffset] = useState(0); // 0 = this month, -1 = last month, etc.

  // Daily date state
  const [singleDate, setSingleDate] = useState(new Date().toISOString().slice(0, 10));

  const [reportData, setReportData] = useState(null);
  const [loading, setLoading] = useState(true);

  // Fetch available locations
  useEffect(() => {
    api.get("/locations").then((r) => {
      if (r?.data && Array.isArray(r.data) && r.data.length > 0) {
        setLocations(r.data);
      }
    }).catch(() => {});
  }, []);

  // Compute start_date and end_date based on period and offsets
  const dateRange = useMemo(() => {
    const now = new Date();

    if (period === "daily") {
      return {
        startDate: singleDate,
        endDate: singleDate,
        displayLabel: singleDate,
      };
    }

    if (period === "weekly") {
      // Calculate Monday of target week
      const target = new Date();
      target.setDate(target.getDate() + (weekOffset * 7));
      const day = target.getDay(); // 0 is Sun, 1 is Mon
      const diffToMonday = (day === 0 ? -6 : 1) - day;
      const monday = new Date(target);
      monday.setDate(target.getDate() + diffToMonday);

      const sunday = new Date(monday);
      sunday.setDate(monday.getDate() + 6);

      const sStr = monday.toISOString().slice(0, 10);
      const eStr = sunday.toISOString().slice(0, 10);

      const sFormatted = monday.toLocaleDateString("en-US", { month: "short", day: "numeric" });
      const eFormatted = sunday.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });

      return {
        startDate: sStr,
        endDate: eStr,
        displayLabel: `${sFormatted} – ${eFormatted}`,
      };
    }

    // Monthly
    const targetMonthDate = new Date(now.getFullYear(), now.getMonth() + monthOffset, 1);
    const yyyy = targetMonthDate.getFullYear();
    const mm = targetMonthDate.getMonth();
    const firstDay = new Date(yyyy, mm, 1);
    const lastDay = new Date(yyyy, mm + 1, 0);

    const sStr = `${yyyy}-${String(mm + 1).padStart(2, "0")}-01`;
    const eStr = `${yyyy}-${String(mm + 1).padStart(2, "0")}-${String(lastDay.getDate()).padStart(2, "0")}`;
    const displayLabel = firstDay.toLocaleDateString("en-US", { month: "long", year: "numeric" });

    return {
      startDate: sStr,
      endDate: eStr,
      displayLabel,
    };
  }, [period, weekOffset, monthOffset, singleDate]);

  const loadReport = useCallback(async () => {
    setLoading(true);
    try {
      const locParam = selectedLocation ? `&location=${selectedLocation}` : "";
      const url = `/reports/summary?period=${period}&start_date=${dateRange.startDate}&end_date=${dateRange.endDate}${locParam}`;
      const { data } = await api.get(url);
      setReportData(data);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || "Failed to load report");
    } finally {
      setLoading(false);
    }
  }, [period, dateRange, selectedLocation]);

  useEffect(() => {
    loadReport();
  }, [loadReport]);

  const summary = reportData?.summary || {};
  const trainers = reportData?.trainer_performance || [];
  const dailyProgression = reportData?.daily_progression || [];
  const newStudents = reportData?.new_students || [];
  const recentClasses = reportData?.recent_classes || [];
  const payments = reportData?.payments || [];
  const paymentMethods = reportData?.payment_methods || {};

  return (
    <div data-testid="reports-page">
      {/* Header */}
      <div className="flex items-end justify-between mb-6 gap-4 flex-wrap">
        <div>
          <div className="label-tag flex items-center gap-1.5">
            <ChartLine size={13} weight="bold" /> Operations &amp; Performance
          </div>
          <h1 className="font-heading text-4xl sm:text-5xl lg:text-6xl font-black tracking-tighter leading-none mt-2">
            Weekly &amp; Monthly Reports
          </h1>
          <p className="text-sm text-zinc-600 mt-2">
            Location-wise branch metrics, completed classes, student progress, and trainer attendance.
          </p>
        </div>

        {/* Filters and Controls */}
        <div className="flex items-end gap-3 flex-wrap">
          {/* Branch Location Dropdown */}
          <div>
            <div className="label-tag mb-1 flex items-center gap-1">
              <MapPin size={11} weight="bold" /> Branch Location
            </div>
            {isAdmin ? (
              <select
                value={selectedLocation}
                onChange={(e) => setSelectedLocation(e.target.value)}
                className="border border-zinc-300 px-3 py-2 text-xs font-bold uppercase tracking-wider bg-white outline-none cursor-pointer"
                data-testid="report-branch-filter"
              >
                <option value="">All Branches</option>
                {locations.map((loc) => (
                  <option key={loc} value={loc}>{loc} Branch</option>
                ))}
              </select>
            ) : (
              <div className="inline-flex items-center gap-1.5 px-3 py-2 bg-blue-50 border border-blue-200 text-blue-900 text-xs font-bold uppercase tracking-wider">
                <span>📍 {user?.location || "Khajaguda"} Branch</span>
              </div>
            )}
          </div>

          <button
            onClick={loadReport}
            className="p-2 border border-zinc-300 hover:bg-zinc-100 transition-colors"
            title="Refresh Report"
          >
            <ArrowClockwise size={16} weight="bold" className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {/* Period Selector Tabs and Navigator Bar */}
      <div className="flex items-center justify-between gap-4 mb-6 flex-wrap pb-4 border-b border-zinc-200">
        {/* Period Tabs */}
        <div className="flex border border-zinc-300 bg-white">
          <button
            onClick={() => setPeriod("weekly")}
            className={`px-4 py-2 text-xs font-bold uppercase tracking-wider transition-colors ${
              period === "weekly" ? "bg-zinc-900 text-white" : "text-zinc-600 hover:bg-zinc-100"
            }`}
          >
            Weekly Report
          </button>
          <button
            onClick={() => setPeriod("monthly")}
            className={`px-4 py-2 text-xs font-bold uppercase tracking-wider border-l border-zinc-300 transition-colors ${
              period === "monthly" ? "bg-zinc-900 text-white" : "text-zinc-600 hover:bg-zinc-100"
            }`}
          >
            Monthly Report
          </button>
          <button
            onClick={() => setPeriod("daily")}
            className={`px-4 py-2 text-xs font-bold uppercase tracking-wider border-l border-zinc-300 transition-colors ${
              period === "daily" ? "bg-zinc-900 text-white" : "text-zinc-600 hover:bg-zinc-100"
            }`}
          >
            Daily Summary
          </button>
        </div>

        {/* Date Navigator */}
        <div className="flex items-center gap-2">
          {period === "weekly" && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setWeekOffset((prev) => prev - 1)}
                className="p-2 border border-zinc-300 hover:bg-zinc-100 transition-colors"
                title="Previous Week"
              >
                <CaretLeft size={14} weight="bold" />
              </button>
              <div className="font-heading font-black text-sm px-3 py-1.5 bg-white border border-zinc-200">
                {dateRange.displayLabel}
              </div>
              <button
                onClick={() => setWeekOffset((prev) => prev + 1)}
                className="p-2 border border-zinc-300 hover:bg-zinc-100 transition-colors"
                title="Next Week"
              >
                <CaretRight size={14} weight="bold" />
              </button>
              {weekOffset !== 0 && (
                <button
                  onClick={() => setWeekOffset(0)}
                  className="text-[10px] font-bold uppercase px-2 py-1 bg-zinc-100 hover:bg-zinc-200"
                >
                  This Week
                </button>
              )}
            </div>
          )}

          {period === "monthly" && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setMonthOffset((prev) => prev - 1)}
                className="p-2 border border-zinc-300 hover:bg-zinc-100 transition-colors"
                title="Previous Month"
              >
                <CaretLeft size={14} weight="bold" />
              </button>
              <div className="font-heading font-black text-sm px-3 py-1.5 bg-white border border-zinc-200">
                {dateRange.displayLabel}
              </div>
              <button
                onClick={() => setMonthOffset((prev) => prev + 1)}
                className="p-2 border border-zinc-300 hover:bg-zinc-100 transition-colors"
                title="Next Month"
              >
                <CaretRight size={14} weight="bold" />
              </button>
              {monthOffset !== 0 && (
                <button
                  onClick={() => setMonthOffset(0)}
                  className="text-[10px] font-bold uppercase px-2 py-1 bg-zinc-100 hover:bg-zinc-200"
                >
                  This Month
                </button>
              )}
            </div>
          )}

          {period === "daily" && (
            <div className="flex items-center gap-2">
              <input
                type="date"
                value={singleDate}
                onChange={(e) => setSingleDate(e.target.value)}
                className="border border-zinc-300 px-3 py-1.5 text-sm font-mono-data bg-white"
              />
              {singleDate !== new Date().toISOString().slice(0, 10) && (
                <button
                  onClick={() => setSingleDate(new Date().toISOString().slice(0, 10))}
                  className="text-[10px] font-bold uppercase px-2 py-1 bg-zinc-100 hover:bg-zinc-200"
                >
                  Today
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {loading ? (
        <div className="label-tag animate-pulse py-12 text-center">Loading Report Data…</div>
      ) : (
        <div className="space-y-6">
          {/* Summary Metric Bento Cards */}
          <div className={`grid grid-cols-2 ${isAdmin ? "lg:grid-cols-5" : "lg:grid-cols-4"} gap-4`}>
            <MetricCard
              label="Classes Conducted"
              value={summary.classes_conducted || 0}
              sub={`${summary.classes_missed || 0} missed`}
              color="text-zinc-900"
            />
            <MetricCard
              label="New Enrollments"
              value={summary.new_enrollments || 0}
              sub="12-day working plan"
              color="text-blue-700"
            />
            <MetricCard
              label="Active Students"
              value={summary.active_students || 0}
              sub={`${summary.completed_students || 0} completed`}
              color="text-emerald-700"
            />
            <MetricCard
              label="Active Trainers"
              value={summary.active_trainers || 0}
              sub={selectedLocation ? `${selectedLocation} branch` : "All branches"}
              color="text-purple-700"
            />
            {isAdmin && (
              <MetricCard
                label="Fees Collected"
                value={`₹${(summary.total_fees_collected || 0).toLocaleString("en-IN")}`}
                sub="Total period revenue"
                color="text-yellow-700"
              />
            )}
          </div>

          {/* Daily Progression Chart / Bars */}
          {dailyProgression.length > 0 && (
            <div className="bento p-6 bg-white shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <div className="label-tag">Session Volume</div>
                  <h3 className="font-heading text-xl font-bold tracking-tight mt-0.5">
                    Class Sessions Progression ({dateRange.displayLabel})
                  </h3>
                </div>
                <div className="text-xs text-zinc-500 font-mono-data">
                  {summary.classes_conducted} total sessions
                </div>
              </div>

              <div className="grid grid-cols-7 sm:grid-cols-7 md:grid-cols-7 gap-2">
                {dailyProgression.map((d) => {
                  const isSun = d.day_name === "Sun";
                  return (
                    <div
                      key={d.date}
                      className={`p-3 border text-center flex flex-col justify-between min-h-20 ${
                        isSun ? "bg-amber-50/50 border-amber-200" : "bg-zinc-50/70 border-zinc-200"
                      }`}
                    >
                      <div>
                        <div className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">
                          {d.day_name}
                        </div>
                        <div className="font-mono-data text-xs text-zinc-700 font-bold">
                          {d.date.slice(5)}
                        </div>
                      </div>
                      <div className="mt-2">
                        {isSun ? (
                          <span className="text-[9px] font-bold text-amber-700 bg-amber-100 px-1 py-0.5">
                            Sunday Off
                          </span>
                        ) : (
                          <div className="font-heading text-xl font-black text-zinc-900">
                            {d.classes_count}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Trainer Performance & Attendance Leaderboard */}
          <div className="bento p-6 bg-white shadow-sm">
            <div className="flex items-center justify-between mb-4 pb-3 border-b border-zinc-200">
              <div className="flex items-center gap-2">
                <Motorcycle size={18} weight="bold" className="text-zinc-800" />
                <h3 className="font-heading text-xl font-bold tracking-tight">
                  Trainer Performance &amp; Attendance ({trainers.length})
                </h3>
              </div>
              <span className="text-xs text-zinc-500">
                Sorted by classes conducted
              </span>
            </div>

            {trainers.length === 0 ? (
              <div className="py-8 text-center text-xs text-zinc-500 italic">
                No trainers found for {selectedLocation || "all branches"}.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-zinc-50 text-zinc-600 font-bold uppercase tracking-wider border-b border-zinc-200">
                    <tr>
                      <th className="py-3 px-3">Trainer</th>
                      <th className="py-3 px-3">Branch Location</th>
                      <th className="py-3 px-3 text-center">Classes Conducted</th>
                      <th className="py-3 px-3 text-center">Days Present</th>
                      <th className="py-3 px-3 text-center">Days Absent</th>
                      <th className="py-3 px-3 text-center">Attendance %</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100">
                    {trainers.map((t) => (
                      <tr key={t.id} className="hover:bg-zinc-50/50">
                        <td className="py-3 px-3">
                          <Link to={`/trainers/${t.id}`} className="font-heading text-sm font-bold text-zinc-900 hover:text-blue-700">
                            {t.name}
                          </Link>
                          {t.phone && <div className="text-[11px] text-zinc-500 font-mono-data">{t.phone}</div>}
                        </td>
                        <td className="py-3 px-3">
                          <span className="font-mono-data font-bold text-zinc-700">
                            📍 {t.location || "Khajaguda"}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-center font-heading text-lg font-black text-zinc-900">
                          {t.classes_conducted}
                        </td>
                        <td className="py-3 px-3 text-center">
                          <span className="inline-flex items-center gap-1 font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 border border-emerald-200">
                            <CheckCircle size={11} weight="bold" /> {t.present_days}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-center">
                          <span className="inline-flex items-center gap-1 font-bold text-red-700 bg-red-50 px-2 py-0.5 border border-red-200">
                            <XCircle size={11} weight="bold" /> {t.absent_days}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-center">
                          <span className="font-mono-data font-bold text-zinc-800">
                            {t.attendance_rate}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Grid: New Students Enrolled + Conducted Classes */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* New Students Enrolled */}
            <div className="bento p-6 bg-white shadow-sm">
              <div className="flex items-center justify-between mb-4 pb-3 border-b border-zinc-200">
                <div className="flex items-center gap-2">
                  <Users size={18} weight="bold" className="text-zinc-800" />
                  <h3 className="font-heading text-xl font-bold tracking-tight">
                    New Enrollments ({newStudents.length})
                  </h3>
                </div>
              </div>

              {newStudents.length === 0 ? (
                <div className="py-8 text-center text-xs text-zinc-500 italic">
                  No new student enrollments in this period.
                </div>
              ) : (
                <div className="overflow-x-auto max-h-80 overflow-y-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-zinc-50 text-zinc-600 font-bold uppercase tracking-wider sticky top-0">
                      <tr>
                        <th className="py-2.5 px-3">Student</th>
                        <th className="py-2.5 px-3">Branch</th>
                        <th className="py-2.5 px-3">Assigned Trainer</th>
                        <th className="py-2.5 px-3">Slot</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-100">
                      {newStudents.map((s) => (
                        <tr key={s.id} className="hover:bg-zinc-50/50">
                          <td className="py-2.5 px-3">
                            <Link to={`/students/${s.id}`} className="font-bold text-zinc-900 hover:text-blue-700">
                              {s.name}
                            </Link>
                            <div className="text-[10px] text-zinc-500 font-mono-data">{s.joining_date}</div>
                          </td>
                          <td className="py-2.5 px-3 font-mono-data text-zinc-700">{s.location}</td>
                          <td className="py-2.5 px-3 font-semibold text-zinc-800">{s.assigned_trainer_name}</td>
                          <td className="py-2.5 px-3 font-mono-data text-zinc-600">{s.slot_time || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Conducted Class Sessions */}
            <div className="bento p-6 bg-white shadow-sm">
              <div className="flex items-center justify-between mb-4 pb-3 border-b border-zinc-200">
                <div className="flex items-center gap-2">
                  <Clock size={18} weight="bold" className="text-zinc-800" />
                  <h3 className="font-heading text-xl font-bold tracking-tight">
                    Conducted Classes ({recentClasses.length})
                  </h3>
                </div>
              </div>

              {recentClasses.length === 0 ? (
                <div className="py-8 text-center text-xs text-zinc-500 italic">
                  No completed class records in this period.
                </div>
              ) : (
                <div className="overflow-x-auto max-h-80 overflow-y-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-zinc-50 text-zinc-600 font-bold uppercase tracking-wider sticky top-0">
                      <tr>
                        <th className="py-2.5 px-3">Date</th>
                        <th className="py-2.5 px-3">Student</th>
                        <th className="py-2.5 px-3">Trainer</th>
                        <th className="py-2.5 px-3 text-right">Class #</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-100">
                      {recentClasses.map((c) => (
                        <tr key={c.id} className="hover:bg-zinc-50/50">
                          <td className="py-2.5 px-3 font-mono-data text-zinc-600">{c.completed_date}</td>
                          <td className="py-2.5 px-3 font-bold text-zinc-900">
                            <Link to={`/students/${c.student_id}`} className="hover:text-blue-700">
                              {c.student_name}
                            </Link>
                          </td>
                          <td className="py-2.5 px-3 text-zinc-700">{c.trainer_name}</td>
                          <td className="py-2.5 px-3 text-right font-mono-data font-bold text-zinc-900">
                            #{c.class_number}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>

          {/* Admin Only: Payments & Revenue Breakdown */}
          {isAdmin && (
            <div className="bento p-6 bg-white shadow-sm">
              <div className="flex items-center justify-between mb-4 pb-3 border-b border-zinc-200 flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <CurrencyInr size={20} weight="bold" className="text-yellow-700" />
                  <h3 className="font-heading text-xl font-bold tracking-tight">
                    Revenue &amp; Collections Ledger (Admin Only)
                  </h3>
                </div>
                <div className="flex items-center gap-2">
                  {Object.entries(paymentMethods).map(([m, val]) => (
                    <span key={m} className="px-2 py-0.5 bg-zinc-100 border border-zinc-200 text-xs font-mono-data font-bold uppercase">
                      {m}: ₹{val.toLocaleString("en-IN")}
                    </span>
                  ))}
                </div>
              </div>

              {payments.length === 0 ? (
                <div className="py-8 text-center text-xs text-zinc-500 italic">
                  No payment transactions recorded during this period.
                </div>
              ) : (
                <div className="overflow-x-auto max-h-80 overflow-y-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-zinc-50 text-zinc-600 font-bold uppercase tracking-wider sticky top-0">
                      <tr>
                        <th className="py-2.5 px-3">Date</th>
                        <th className="py-2.5 px-3">Amount</th>
                        <th className="py-2.5 px-3">Method</th>
                        <th className="py-2.5 px-3">Notes</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-100">
                      {payments.map((p) => (
                        <tr key={p.id} className="hover:bg-zinc-50/50">
                          <td className="py-2.5 px-3 font-mono-data font-bold text-zinc-700">{p.date}</td>
                          <td className="py-2.5 px-3 font-heading font-black text-sm text-yellow-800">
                            ₹{Number(p.amount).toLocaleString("en-IN")}
                          </td>
                          <td className="py-2.5 px-3 uppercase font-bold text-zinc-600">{p.method}</td>
                          <td className="py-2.5 px-3 text-zinc-500 italic">{p.notes || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function MetricCard({ label, value, sub, color = "text-zinc-900" }) {
  return (
    <div className="bento p-5 bg-white shadow-sm">
      <div className="label-tag">{label}</div>
      <div className={`font-heading text-3xl font-black tracking-tighter mt-1 ${color}`}>
        {value}
      </div>
      {sub && <div className="text-[11px] text-zinc-500 mt-1 font-mono-data">{sub}</div>}
    </div>
  );
}
