import React, { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { formatSlot12 } from "@/lib/utils";
import { useAuth } from "@/context/AuthContext";
import {
  Clock,
  Phone,
  Truck,
  CheckCircle,
  XCircle,
  User,
  Star,
  CalendarBlank,
  Plus,
  Trash,
  CaretLeft,
  CaretRight,
  Sparkle,
  X,
} from "@phosphor-icons/react";
import { toast } from "sonner";
import CopyButton from "@/components/CopyButton";

export default function Schedule() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const isManager = user?.role === "manager";
  const isManagerOrAdmin = isAdmin || isManager;

  const [viewMode, setViewMode] = useState("daily"); // "daily" | "calendar"
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all"); // all | mine
  const [locations, setLocations] = useState(["Attapur", "Khajaguda", "Madhapur"]);
  const [selectedLocation, setSelectedLocation] = useState(isManagerOrAdmin ? "" : (user?.location || "Khajaguda"));

  // Monthly Calendar & Holidays state
  const [calYear, setCalYear] = useState(new Date().getFullYear());
  const [calMonth, setCalMonth] = useState(new Date().getMonth()); // 0-indexed
  const [holidays, setHolidays] = useState([]);
  const [loadingHolidays, setLoadingHolidays] = useState(false);

  // Holiday Modal state
  const [holidayModalOpen, setHolidayModalOpen] = useState(false);
  const [submittingHoliday, setSubmittingHoliday] = useState(false);
  const [holidayForm, setHolidayForm] = useState({
    date: new Date().toISOString().slice(0, 10),
    title: "",
    type: "holiday",
    location: "",
    notes: "",
  });

  useEffect(() => {
    if (user?.role === "trainer") {
      setFilter("mine");
    }
  }, [user]);

  useEffect(() => {
    api.get("/locations").then((r) => {
      if (r?.data && Array.isArray(r.data) && r.data.length > 0) {
        setLocations(r.data);
      }
    }).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    const locParam = selectedLocation ? `&location=${selectedLocation}` : "";
    const { data } = await api.get(`/schedule/today?date=${date}${locParam}`);
    setData(data);
  }, [date, selectedLocation]);

  const loadHolidays = useCallback(async () => {
    setLoadingHolidays(true);
    try {
      const locParam = selectedLocation ? `&location=${selectedLocation}` : "";
      const res = await api.get(`/holidays?year=${calYear}&month=${calMonth + 1}${locParam}`);
      setHolidays(res.data || []);
    } catch (e) {
      toast.error("Failed to load holidays");
    } finally {
      setLoadingHolidays(false);
    }
  }, [calYear, calMonth, selectedLocation]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try { await load(); } finally { setLoading(false); }
    })();
  }, [load]);

  useEffect(() => {
    if (viewMode === "calendar") {
      loadHolidays();
    }
  }, [viewMode, loadHolidays]);

  const trainerName = (id) =>
    data?.trainers.find((t) => t.id === id)?.name || "—";

  const isMine = (row) =>
    user && (row.assigned_trainer_id === user.id || row.pickup_trainer_id === user.id || row.drop_trainer_id === user.id);

  const filterRows = (rows) => filter === "mine" ? rows.filter(isMine) : rows;

  const myCounts = (() => {
    if (!data || !user) return null;
    let pickups = 0, drops = 0, classes = 0;
    Object.values(data.by_slot || {}).forEach((rows) => {
      rows.forEach((r) => {
        if (r.pickup_trainer_id === user.id) pickups++;
        if (r.drop_trainer_id === user.id) drops++;
        if (r.assigned_trainer_id === user.id) classes++;
      });
    });
    (data.unassigned || []).forEach((r) => {
      if (r.pickup_trainer_id === user.id) pickups++;
      if (r.drop_trainer_id === user.id) drops++;
      if (r.assigned_trainer_id === user.id) classes++;
    });
    return { pickups, drops, classes };
  })();

  const markClass = async (classId, status, studentName, num) => {
    try {
      const payload = { status };
      if (status === "completed") payload.completed_date = date;
      await api.patch(`/classes/${classId}`, payload);
      const label = status === "completed" ? "Present" : status === "absent" ? "Absent" : status;
      toast.success(`Class ${num} for ${studentName} marked ${label}`);
      load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    }
  };

  const handleOpenHolidayModal = (initialDate = "") => {
    setHolidayForm({
      date: initialDate || date || new Date().toISOString().slice(0, 10),
      title: "",
      type: "holiday",
      location: isManager ? (user?.location || "") : (selectedLocation || ""),
      notes: "",
    });
    setHolidayModalOpen(true);
  };

  const handleCreateHoliday = async (e) => {
    e.preventDefault();
    if (!holidayForm.title.trim()) {
      toast.error("Please enter a title for the holiday or function");
      return;
    }
    setSubmittingHoliday(true);
    try {
      const payload = {
        date: holidayForm.date,
        title: holidayForm.title.trim(),
        type: holidayForm.type,
        location: holidayForm.location || null,
        notes: holidayForm.notes.trim() || null,
      };
      await api.post("/holidays", payload);
      toast.success(`${holidayForm.type === "function" ? "Function" : "Holiday"} added! Working days automatically rescheduled.`);
      setHolidayModalOpen(false);
      loadHolidays();
      load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setSubmittingHoliday(false);
    }
  };

  const handleDeleteHoliday = async (holidayId, title) => {
    if (!window.confirm(`Delete declared holiday "${title}"?`)) return;
    try {
      await api.delete(`/holidays/${holidayId}`);
      toast.success(`Holiday removed`);
      loadHolidays();
      load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    }
  };

  const prevMonth = () => {
    if (calMonth === 0) {
      setCalMonth(11);
      setCalYear(calYear - 1);
    } else {
      setCalMonth(calMonth - 1);
    }
  };

  const nextMonth = () => {
    if (calMonth === 11) {
      setCalMonth(0);
      setCalYear(calYear + 1);
    } else {
      setCalMonth(calMonth + 1);
    }
  };

  // Calendar calculations for selected month
  const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();
  const startDayOfWeek = new Date(calYear, calMonth, 1).getDay(); // 0 = Sun
  const monthName = new Date(calYear, calMonth, 1).toLocaleDateString("en-US", { month: "long" });

  const calendarDays = [];
  for (let d = 1; d <= daysInMonth; d++) {
    const dt = new Date(calYear, calMonth, d);
    const dayName = dt.toLocaleDateString("en-US", { weekday: "short" });
    const isSunday = dt.getDay() === 0;
    const yyyy = calYear;
    const mm = String(calMonth + 1).padStart(2, "0");
    const dd = String(d).padStart(2, "0");
    const dateStr = `${yyyy}-${mm}-${dd}`;
    const dayHolidays = holidays.filter((h) => h.date === dateStr);
    calendarDays.push({
      dayNum: d,
      dayName,
      isSunday,
      dateStr,
      holidays: dayHolidays,
    });
  }

  return (
    <div data-testid="schedule-page">
      <div className="flex items-end justify-between mb-6 gap-4 flex-wrap">
        <div>
          <div className="label-tag">Schedule & Calendar</div>
          <h1 className="font-heading text-4xl sm:text-5xl lg:text-6xl font-black tracking-tighter leading-none mt-2">
            Schedule & Operations
          </h1>
          <p className="text-sm text-zinc-600 mt-2">
            10-day working schedules, slot-wise daily ops roster, and functions/holidays calendar.
          </p>
        </div>
        <div className="flex items-end gap-3 flex-wrap">
          {isManagerOrAdmin ? (
            <div>
              <div className="label-tag mb-1">Branch</div>
              <select
                value={selectedLocation}
                onChange={(e) => setSelectedLocation(e.target.value)}
                className="border border-zinc-300 px-3 py-2 text-xs font-bold uppercase tracking-wider bg-white outline-none cursor-pointer"
                data-testid="schedule-branch-filter"
              >
                {isManagerOrAdmin && <option value="">All Branches</option>}
                {locations.map((loc) => (
                  <option key={loc} value={loc}>{loc} Branch</option>
                ))}
              </select>
            </div>
          ) : (
            <div className="inline-flex items-center gap-1.5 px-3 py-2 bg-blue-50 border border-blue-200 text-blue-900 text-xs font-bold uppercase tracking-wider mb-0.5">
              <span>📍 {user?.location || "Khajaguda"} Branch</span>
            </div>
          )}

          {viewMode === "daily" && (
            <>
              <div>
                <div className="label-tag mb-1">View</div>
                <div className="flex border border-zinc-300">
                  <button
                    onClick={() => setFilter("all")}
                    data-testid="filter-all"
                    className={`px-3 py-2 text-xs font-bold uppercase tracking-wider ${filter === "all" ? "bg-zinc-900 text-white" : "hover:bg-zinc-100"}`}
                  >All</button>
                  <button
                    onClick={() => setFilter("mine")}
                    data-testid="filter-mine"
                    className={`px-3 py-2 text-xs font-bold uppercase tracking-wider border-l border-zinc-300 ${filter === "mine" ? "bg-zinc-900 text-white" : "hover:bg-zinc-100"}`}
                  >Mine</button>
                </div>
              </div>
              <div>
                <div className="label-tag mb-1">Date</div>
                <input
                  type="date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  data-testid="schedule-date"
                  className="border border-zinc-300 px-3 py-2 text-sm font-mono-data"
                />
              </div>
            </>
          )}

          {viewMode === "calendar" && isManagerOrAdmin && (
            <button
              onClick={() => handleOpenHolidayModal()}
              className="inline-flex items-center gap-2 bg-purple-700 hover:bg-purple-800 text-white px-4 py-2 text-xs font-bold uppercase tracking-wider transition-colors shadow-sm"
            >
              <Plus size={14} weight="bold" /> Declare Holiday / Function
            </button>
          )}
        </div>
      </div>

      {/* View Mode Switcher Tabs */}
      <div className="flex border border-zinc-300 mb-6 w-fit bg-white">
        <button
          onClick={() => setViewMode("daily")}
          className={`px-5 py-2.5 text-xs font-bold uppercase tracking-wider flex items-center gap-2 transition-colors ${
            viewMode === "daily" ? "bg-zinc-900 text-white" : "text-zinc-600 hover:bg-zinc-100"
          }`}
        >
          <Clock size={15} weight="bold" /> Daily Ops Schedule
        </button>
        <button
          onClick={() => setViewMode("calendar")}
          className={`px-5 py-2.5 text-xs font-bold uppercase tracking-wider flex items-center gap-2 border-l border-zinc-300 transition-colors ${
            viewMode === "calendar" ? "bg-zinc-900 text-white" : "text-zinc-600 hover:bg-zinc-100"
          }`}
        >
          <CalendarBlank size={15} weight="bold" /> Calendar & Holidays
        </button>
      </div>

      {/* ---------- DAILY OPS VIEW ---------- */}
      {viewMode === "daily" && (
        <>
          {/* Holiday / Function or Sunday Notice Banner */}
          {data?.holiday && (
            <div className="mb-6 p-4 bg-purple-50 border-2 border-purple-300 flex items-center justify-between gap-4 flex-wrap">
              <div className="flex items-center gap-3">
                <div className="px-2.5 py-1.5 bg-purple-700 text-white font-black text-xs uppercase tracking-wider">
                  {data.holiday.type === "function" ? "🎪 Special Function" : "🎉 Official Holiday"}
                </div>
                <div>
                  <div className="font-heading font-black text-xl text-purple-950 flex items-center gap-2">
                    <span>{data.holiday.title}</span>
                    <span className="text-[10px] px-2 py-0.5 bg-purple-200 text-purple-900 font-bold uppercase tracking-wider">
                      {data.holiday.location ? `${data.holiday.location} Branch` : "All Branches"}
                    </span>
                  </div>
                  <p className="text-xs text-purple-800 mt-1">
                    {data.holiday.notes || "Official driving school off/function day. Student 10-day working schedules automatically skip this date."}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <span className="text-xs font-mono-data font-bold text-purple-800 bg-purple-100 border border-purple-200 px-3 py-1.5 inline-block">
                  No regular classes scheduled today
                </span>
              </div>
            </div>
          )}

          {data?.is_sunday && (
            <div className="mb-6 p-4 bg-amber-50 border-2 border-amber-300 flex items-center justify-between gap-4 flex-wrap">
              <div className="flex items-center gap-3">
                <div className="px-2.5 py-1.5 bg-amber-500 text-zinc-950 font-black text-xs uppercase tracking-wider">
                  ☕ Sunday Weekly Off
                </div>
                <div>
                  <div className="font-heading font-black text-xl text-amber-950">
                    Weekly School Holiday (Sunday)
                  </div>
                  <p className="text-xs text-amber-900 mt-1">
                    Driving school operations are paused on Sundays. Student 10-day working schedules automatically advance past Sundays.
                  </p>
                </div>
              </div>
              <div className="text-right">
                <span className="text-xs font-mono-data font-bold text-amber-800 bg-amber-100 border border-amber-200 px-3 py-1.5 inline-block">
                  Sunday Off Day
                </span>
              </div>
            </div>
          )}

          {myCounts && (
            <div className="bento p-4 mb-4 flex items-center gap-6 flex-wrap" data-testid="my-summary">
              <div className="flex items-center gap-2">
                <Star size={16} weight="fill" className="text-yellow-400" />
                <span className="label-tag">Your tasks today</span>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="font-mono-data text-xs text-zinc-500">Classes</span>
                <span className="font-heading text-xl font-black tracking-tighter">{myCounts.classes}</span>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="font-mono-data text-xs text-zinc-500">Pickups</span>
                <span className="font-heading text-xl font-black tracking-tighter text-yellow-700">{myCounts.pickups}</span>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="font-mono-data text-xs text-zinc-500">Drops</span>
                <span className="font-heading text-xl font-black tracking-tighter text-blue-700">{myCounts.drops}</span>
              </div>
            </div>
          )}

          {loading ? (
            <div className="label-tag animate-pulse">Loading…</div>
          ) : (
            <div className="space-y-4">
              {(data?.slots || []).length === 0 && (
                <div className="bento p-12 text-center">
                  <div className="label-tag mb-2">No slots configured</div>
                  <Link to="/slots" className="text-sm font-bold text-blue-700 hover:underline">
                    + Add time slots in Slots settings
                  </Link>
                </div>
              )}

              {data?.slots.map((slot) => {
                const allRows = data.by_slot[slot.label] || [];
                const rows = filterRows(allRows);
                return (
                  <div key={slot.id} className="bento p-6" data-testid={`slot-${slot.label}`}>
                    <div className="flex items-center justify-between mb-4 pb-4 border-b border-zinc-200 flex-wrap gap-2">
                      <div className="flex items-center gap-3">
                        <div className="bg-zinc-900 text-yellow-400 px-3 py-2">
                          <Clock size={20} weight="bold" />
                        </div>
                        <div>
                          <div className="label-tag">Slot</div>
                          <h2 className="font-heading text-2xl font-black tracking-tighter font-mono-data">
                            {formatSlot12(slot.label)}
                          </h2>
                        </div>
                      </div>
                      <div className="label-tag">{rows.length}{filter === "mine" && allRows.length > rows.length ? ` of ${allRows.length}` : ""} customers</div>
                    </div>

                    {rows.length === 0 ? (
                      <div className="text-xs text-zinc-500 italic py-4">{filter === "mine" ? "Nothing assigned to you in this slot." : "No customers in this slot."}</div>
                    ) : (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {rows.map((r) => (
                          <ScheduleCard
                            key={r.id}
                            row={r}
                            currentUserId={user?.id}
                            trainerName={trainerName}
                            onMark={markClass}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}

              {(() => {
                const unassigned = filterRows(data?.unassigned || []);
                if (unassigned.length === 0) return null;
                return (
                  <div className="bento p-6">
                    <div className="flex items-center justify-between mb-4 pb-4 border-b border-zinc-200">
                      <div>
                        <div className="label-tag">No slot assigned</div>
                        <h2 className="font-heading text-2xl font-black tracking-tighter">
                          Unassigned customers
                        </h2>
                      </div>
                      <div className="label-tag">{unassigned.length}</div>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {unassigned.map((r) => (
                        <ScheduleCard
                          key={r.id}
                          row={r}
                          currentUserId={user?.id}
                          trainerName={trainerName}
                          onMark={markClass}
                        />
                      ))}
                    </div>
                  </div>
                );
              })()}
            </div>
          )}
        </>
      )}

      {/* ---------- CALENDAR & HOLIDAYS VIEW ---------- */}
      {viewMode === "calendar" && (
        <div className="space-y-6">
          <div className="bento p-6 bg-white shadow-sm">
            {/* Calendar Controls & Month Header */}
            <div className="flex items-center justify-between mb-6 pb-4 border-b border-zinc-200 flex-wrap gap-3">
              <div className="flex items-center gap-3">
                <button
                  onClick={prevMonth}
                  className="p-2 border border-zinc-300 hover:bg-zinc-100 transition-colors"
                  title="Previous Month"
                >
                  <CaretLeft size={16} weight="bold" />
                </button>
                <h2 className="font-heading text-2xl font-black tracking-tight">
                  {monthName} {calYear}
                </h2>
                <button
                  onClick={nextMonth}
                  className="p-2 border border-zinc-300 hover:bg-zinc-100 transition-colors"
                  title="Next Month"
                >
                  <CaretRight size={16} weight="bold" />
                </button>
              </div>

              <div className="flex items-center gap-2 text-xs">
                <span className="flex items-center gap-1.5 px-2 py-1 bg-amber-50 text-amber-800 border border-amber-200 font-bold">
                  ☕ Sundays Off
                </span>
                <span className="flex items-center gap-1.5 px-2 py-1 bg-purple-50 text-purple-800 border border-purple-200 font-bold">
                  🎉 Holidays & Functions
                </span>
                <span className="flex items-center gap-1.5 px-2 py-1 bg-emerald-50 text-emerald-800 border border-emerald-200 font-bold">
                  🚗 Working Days
                </span>
              </div>
            </div>

            {loadingHolidays ? (
              <div className="py-12 text-center text-xs font-bold uppercase tracking-wider text-zinc-400 animate-pulse">
                Loading Calendar & Holidays...
              </div>
            ) : (
              <>
                {/* Days of Week Headers */}
                <div className="grid grid-cols-7 gap-2 mb-2 text-center font-mono-data text-xs font-bold text-zinc-500 uppercase">
                  <div className="text-amber-700">Sun</div>
                  <div>Mon</div>
                  <div>Tue</div>
                  <div>Wed</div>
                  <div>Thu</div>
                  <div>Fri</div>
                  <div>Sat</div>
                </div>

                {/* Calendar Days Grid */}
                <div className="grid grid-cols-7 gap-2">
                  {/* Blank placeholder spaces before start day */}
                  {Array.from({ length: startDayOfWeek }).map((_, idx) => (
                    <div key={`blank-${idx}`} className="min-h-24 bg-zinc-50/50 border border-zinc-100" />
                  ))}

                  {calendarDays.map(({ dayNum, isSunday, dateStr, holidays: dayHols }) => {
                    const hasHoliday = dayHols.length > 0;
                    let cellBg = "bg-white border-zinc-200 hover:border-zinc-400";
                    if (isSunday) {
                      cellBg = "bg-amber-50/40 border-amber-200/80";
                    } else if (hasHoliday) {
                      cellBg = "bg-purple-50 border-purple-300";
                    }

                    return (
                      <div
                        key={`cal-${dayNum}`}
                        className={`min-h-24 border p-2 flex flex-col justify-between transition-all relative ${cellBg}`}
                      >
                        <div className="flex items-center justify-between">
                          <span className={`font-mono-data text-xs font-bold ${
                            isSunday ? "text-amber-800" : hasHoliday ? "text-purple-900" : "text-zinc-700"
                          }`}>
                            {dayNum}
                          </span>
                          {isSunday && (
                            <span className="text-[8px] uppercase tracking-wider font-extrabold text-amber-700 px-1 py-0.5 bg-amber-100">
                              Sunday Off
                            </span>
                          )}
                        </div>

                        {/* Holiday or Function badges */}
                        <div className="space-y-1 my-1">
                          {dayHols.map((h) => (
                            <div
                              key={h.id}
                              className="text-[9px] p-1 bg-purple-600 text-white font-bold leading-tight flex items-start justify-between gap-1 shadow-xs"
                              title={`${h.title} (${h.type}) - ${h.location || "All Branches"}${h.notes ? ` - ${h.notes}` : ""}`}
                            >
                              <span className="truncate">
                                {h.type === "function" ? "🎪" : "🎉"} {h.title}
                              </span>
                              {isManagerOrAdmin && (
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleDeleteHoliday(h.id, h.title);
                                  }}
                                  className="text-purple-200 hover:text-white"
                                  title="Delete holiday"
                                >
                                  <X size={10} weight="bold" />
                                </button>
                              )}
                            </div>
                          ))}
                        </div>

                        {/* Quick actions for this date */}
                        <div className="flex items-center justify-between pt-1 border-t border-zinc-100">
                          <button
                            type="button"
                            onClick={() => {
                              setDate(dateStr);
                              setViewMode("daily");
                            }}
                            className="text-[9px] font-bold uppercase tracking-wider text-blue-700 hover:underline"
                          >
                            View Ops →
                          </button>
                          {isManagerOrAdmin && !hasHoliday && !isSunday && (
                            <button
                              type="button"
                              onClick={() => handleOpenHolidayModal(dateStr)}
                              className="text-[9px] font-bold text-zinc-400 hover:text-purple-700"
                              title="Declare Holiday or Function on this date"
                            >
                              + Off
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </div>

          {/* List of Declared Holidays & Functions for Month */}
          <div className="bento p-6 bg-white shadow-sm">
            <div className="flex items-center justify-between mb-4 pb-3 border-b border-zinc-200">
              <div className="flex items-center gap-2">
                <Sparkle size={18} className="text-purple-600" weight="bold" />
                <h3 className="font-heading text-xl font-bold tracking-tight">
                  Declared Holidays & School Functions ({holidays.length})
                </h3>
              </div>
              {isManagerOrAdmin && (
                <button
                  onClick={() => handleOpenHolidayModal()}
                  className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-purple-700 hover:text-purple-900"
                >
                  <Plus size={12} weight="bold" /> Add for {monthName}
                </button>
              )}
            </div>

            {holidays.length === 0 ? (
              <div className="py-8 text-center text-xs text-zinc-500 italic">
                No special holidays or functions declared for {monthName} {calYear}. Only Sundays are treated as weekly off.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-zinc-50 text-zinc-600 font-bold uppercase tracking-wider border-b border-zinc-200">
                    <tr>
                      <th className="py-2.5 px-3">Date</th>
                      <th className="py-2.5 px-3">Title</th>
                      <th className="py-2.5 px-3">Type</th>
                      <th className="py-2.5 px-3">Branch</th>
                      <th className="py-2.5 px-3">Notes</th>
                      {isManagerOrAdmin && <th className="py-2.5 px-3 text-right">Actions</th>}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-200">
                    {holidays.map((h) => (
                      <tr key={h.id} className="hover:bg-zinc-50/50">
                        <td className="py-3 px-3 font-mono-data font-bold text-zinc-800">{h.date}</td>
                        <td className="py-3 px-3 font-heading text-sm font-bold text-zinc-900">{h.title}</td>
                        <td className="py-3 px-3">
                          <span className={`px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                            h.type === "function" ? "bg-amber-100 text-amber-900" : "bg-purple-100 text-purple-900"
                          }`}>
                            {h.type}
                          </span>
                        </td>
                        <td className="py-3 px-3">
                          <span className="font-mono-data text-zinc-600">
                            {h.location ? `${h.location} Branch` : "All Branches"}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-zinc-500 italic max-w-xs truncate">
                          {h.notes || "—"}
                        </td>
                        {isManagerOrAdmin && (
                          <td className="py-3 px-3 text-right">
                            <button
                              onClick={() => handleDeleteHoliday(h.id, h.title)}
                              className="text-red-600 hover:text-red-800 p-1 transition-colors"
                              title="Delete declared holiday"
                            >
                              <Trash size={14} weight="bold" />
                            </button>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ---------- DECLARE HOLIDAY / FUNCTION MODAL ---------- */}
      {holidayModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-zinc-900/60 backdrop-blur-xs">
          <div className="bg-white border-2 border-zinc-900 w-full max-w-md p-6 shadow-xl animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between pb-3 mb-4 border-b border-zinc-200">
              <div className="flex items-center gap-2">
                <div className="p-1.5 bg-purple-600 text-white">
                  <Sparkle size={16} weight="bold" />
                </div>
                <h3 className="font-heading text-lg font-black tracking-tight">
                  Declare Holiday / Function
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setHolidayModalOpen(false)}
                className="p-1 hover:bg-zinc-100 text-zinc-500"
              >
                <X size={16} weight="bold" />
              </button>
            </div>

            <p className="text-xs text-zinc-600 mb-4 leading-relaxed">
              Declare festival holidays, school functions, fleet inspection, or special off-days.
              All active student 10-day schedules will automatically skip this date.
            </p>

            <form onSubmit={handleCreateHoliday} className="space-y-4">
              <div>
                <label className="label-tag block mb-1">Date *</label>
                <input
                  type="date"
                  required
                  value={holidayForm.date}
                  onChange={(e) => setHolidayForm({ ...holidayForm, date: e.target.value })}
                  className="w-full border border-zinc-300 px-3 py-2 text-sm font-mono-data bg-white"
                />
              </div>

              <div>
                <label className="label-tag block mb-1">Title *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Diwali Festival, Ayudha Pooja, Annual Function"
                  value={holidayForm.title}
                  onChange={(e) => setHolidayForm({ ...holidayForm, title: e.target.value })}
                  className="w-full border border-zinc-300 px-3 py-2 text-sm bg-white"
                />
              </div>

              <div>
                <label className="label-tag block mb-1">Type *</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setHolidayForm({ ...holidayForm, type: "holiday" })}
                    className={`p-2.5 text-xs font-bold uppercase tracking-wider border text-center transition-all ${
                      holidayForm.type === "holiday"
                        ? "bg-purple-600 text-white border-purple-700"
                        : "bg-white text-zinc-700 border-zinc-300 hover:bg-zinc-50"
                    }`}
                  >
                    🎉 Holiday
                  </button>
                  <button
                    type="button"
                    onClick={() => setHolidayForm({ ...holidayForm, type: "function" })}
                    className={`p-2.5 text-xs font-bold uppercase tracking-wider border text-center transition-all ${
                      holidayForm.type === "function"
                        ? "bg-amber-600 text-white border-amber-700"
                        : "bg-white text-zinc-700 border-zinc-300 hover:bg-zinc-50"
                    }`}
                  >
                    🎪 Function
                  </button>
                </div>
              </div>

              <div>
                <label className="label-tag block mb-1">Location / Branch</label>
                {isManager && user?.location ? (
                  <div className="p-2.5 bg-blue-50 border border-blue-200 text-blue-900 text-xs font-bold">
                    📍 {user.location} Branch (Manager declared)
                  </div>
                ) : (
                  <select
                    value={holidayForm.location}
                    onChange={(e) => setHolidayForm({ ...holidayForm, location: e.target.value })}
                    className="w-full border border-zinc-300 px-3 py-2 text-xs font-bold uppercase tracking-wider bg-white"
                  >
                    <option value="">All Branches</option>
                    {locations.map((loc) => (
                      <option key={loc} value={loc}>{loc} Branch</option>
                    ))}
                  </select>
                )}
              </div>

              <div>
                <label className="label-tag block mb-1">Notes (Optional)</label>
                <textarea
                  rows={2}
                  placeholder="Additional context or timing details..."
                  value={holidayForm.notes}
                  onChange={(e) => setHolidayForm({ ...holidayForm, notes: e.target.value })}
                  className="w-full border border-zinc-300 px-3 py-2 text-xs bg-white"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-zinc-200">
                <button
                  type="button"
                  onClick={() => setHolidayModalOpen(false)}
                  className="px-4 py-2 border border-zinc-300 text-xs font-bold uppercase tracking-wider hover:bg-zinc-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingHoliday}
                  className="px-4 py-2 bg-purple-700 hover:bg-purple-800 text-white text-xs font-bold uppercase tracking-wider disabled:opacity-50"
                >
                  {submittingHoliday ? "Saving…" : "Declare & Reschedule"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function ScheduleCard({ row, trainerName, onMark }) {
  const next = row.next_class;
  const todayCls = row.today_class;
  const targetCls = todayCls || next;
  const isEndingSoon = row.is_ending_soon;

  return (
    <div
      className={`border p-4 transition-colors ${
        isEndingSoon
          ? "border-amber-400 bg-amber-50/50 hover:border-amber-500 shadow-sm"
          : "border-zinc-200 hover:border-zinc-400"
      }`}
      data-testid={`schedule-card-${row.id}`}
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <Link to={`/students/${row.id}`} className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <div className="font-heading text-lg font-bold tracking-tight hover:text-blue-700 truncate">
              {row.name}
            </div>
            {isEndingSoon && (
              <span className="inline-flex items-center gap-1 text-[9px] px-1.5 py-0.5 bg-amber-500 text-white font-black uppercase tracking-wider" title="Slot freeing up in final 3 working days">
                ⚡ {row.classes_remaining}d left
              </span>
            )}
          </div>
          <div className="flex items-center gap-1.5 text-xs text-zinc-600 font-mono-data mt-0.5">
            <span className="flex items-center gap-1"><Phone size={11} weight="bold" /> {row.phone}</span>
            <CopyButton text={row.phone} size={11} title={`Copy ${row.phone}`} successMessage={`Copied phone: ${row.phone}`} />
          </div>
        </Link>
        {row.needs_pickup && (
          <div className="flex items-center gap-1 bg-yellow-400 text-zinc-900 px-2 py-1 text-[10px] font-bold uppercase tracking-wider whitespace-nowrap">
            <Truck size={11} weight="bold" /> Pickup
          </div>
        )}
      </div>

      {row.needs_pickup && row.pickup_address && (
        <div className="text-xs text-zinc-600 bg-zinc-50 border-l-2 border-yellow-400 px-2 py-1.5 mb-3">
          <span className="label-tag block mb-0.5">Pickup</span>
          {row.pickup_address}
        </div>
      )}

      <div className="flex items-center gap-2 text-xs text-zinc-500 mb-3 flex-wrap">
        <span className="inline-flex items-center gap-1">
          <User size={11} weight="bold" />
          {trainerName(row.assigned_trainer_id)}
        </span>
        {targetCls && (
          <span className="font-mono-data">
            · Class {targetCls.class_number}/{row.total_classes || 10}
            {row.classes_absent > 0 && (
              <span className="text-red-600 font-bold ml-1">({row.classes_absent} absent)</span>
            )}{" "}
            ·{" "}
            <span
              className={
                targetCls.status === "completed"
                  ? "text-emerald-700 font-bold"
                  : (targetCls.status === "absent" || targetCls.status === "missed")
                  ? "text-red-700 font-bold"
                  : "text-zinc-500"
              }
            >
              {targetCls.status === "completed"
                ? "✓ Present"
                : (targetCls.status === "absent" || targetCls.status === "missed")
                ? "✗ Absent"
                : targetCls.status}
            </span>
          </span>
        )}
      </div>

      {targetCls && targetCls.status === "pending" && (
        <div className="flex items-center gap-2">
          <button
            onClick={() => onMark(targetCls.id, "completed", row.name, targetCls.class_number)}
            data-testid={`mark-present-${row.id}`}
            className="flex-1 inline-flex items-center justify-center gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-[10px] font-bold uppercase tracking-wider px-3 py-2"
          >
            <CheckCircle size={12} weight="bold" /> Present
          </button>
          <button
            onClick={() => onMark(targetCls.id, "absent", row.name, targetCls.class_number)}
            data-testid={`mark-absent-${row.id}`}
            className="flex-1 inline-flex items-center justify-center gap-1.5 bg-red-600 hover:bg-red-700 text-white text-[10px] font-bold uppercase tracking-wider px-3 py-2"
          >
            <XCircle size={12} weight="bold" /> Absent
          </button>
        </div>
      )}
      {!targetCls && (
        <div className="text-xs text-zinc-400 italic">All classes completed 🎉</div>
      )}
    </div>
  );
}
