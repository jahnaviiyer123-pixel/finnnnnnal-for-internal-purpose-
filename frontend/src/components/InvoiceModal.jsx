import React, { useEffect, useState, useCallback } from "react";
import { api, formatApiError } from "@/lib/api";
import { formatSlot12 } from "@/lib/utils";
import {
  Printer,
  WhatsappLogo,
  X,
  FileText,
  Copy,
  Check,
  PaperPlaneRight,
  ShieldCheck,
  CalendarBlank,
  Clock,
  User,
  CurrencyInr,
  MapPin,
  CheckCircle,
} from "@phosphor-icons/react";
import { toast } from "sonner";

export default function InvoiceModal({ studentId, open, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [customPhone, setCustomPhone] = useState("");
  const [showCustomInput, setShowCustomInput] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (open && studentId) {
      setLoading(true);
      api
        .get(`/students/${studentId}/invoice`)
        .then((res) => setData(res.data))
        .catch((err) => {
          toast.error(formatApiError(err.response?.data?.detail) || "Failed to load invoice");
          onClose();
        })
        .finally(() => setLoading(false));
    }
  }, [open, studentId, onClose]);

  // Keyboard accessibility: dismiss on Escape
  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const handlePrint = () => {
    window.print();
  };

  const formatCleanDate = (dStr) => {
    if (!dStr) return "—";
    try {
      const d = new Date(dStr);
      if (isNaN(d.getTime())) return dStr;
      const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
      const dayName = days[d.getDay()];
      const day = String(d.getDate()).padStart(2, "0");
      const month = months[d.getMonth()];
      const year = d.getFullYear();
      return `${dayName}, ${day}-${month}-${year}`;
    } catch {
      return dStr;
    }
  };

  const formatShortDate = (dStr) => {
    if (!dStr) return "—";
    try {
      const d = new Date(dStr);
      if (isNaN(d.getTime())) return dStr;
      const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      const day = String(d.getDate()).padStart(2, "0");
      const month = months[d.getMonth()];
      const year = d.getFullYear();
      return `${day}-${month}-${year}`;
    } catch {
      return dStr;
    }
  };

  const formatSlotDisplay = (slot) => {
    if (!slot) return "As per schedule below";
    const s = String(slot).trim();
    if (s.includes("AM") || s.includes("PM")) return s;
    const parts = s.split(/[-–]/).map((p) => p.trim());
    if (parts.length === 2) {
      const toHour = (p) => {
        const [hStr] = p.split(":");
        const h = parseInt(hStr, 10);
        if (isNaN(h)) return { str: p, ampm: "" };
        const ampm = h >= 12 ? "PM" : "AM";
        const h12 = h % 12 === 0 ? 12 : h % 12;
        return { h12, ampm };
      };
      const start = toHour(parts[0]);
      const end = toHour(parts[1]);
      if (start.ampm === end.ampm) {
        return `${start.h12}–${end.h12} ${start.ampm}`;
      }
      return `${start.h12} ${start.ampm} – ${end.h12} ${end.ampm}`;
    }
    return formatSlot12(slot);
  };

  const generateMessage = () => {
    if (!data) return "";
    const slotStr = formatSlotDisplay(data.allotment?.slot_hour);
    const trainerName = data.allotment?.assigned_trainer?.name || "Assigned Instructor";
    const trainerPhone = data.allotment?.assigned_trainer?.phone || "—";
    const totalSessions = data.sessions_count || (data.schedule || []).length || 10;

    const scheduleLines = (data.schedule || [])
      .slice(0, totalSessions)
      .map((c) => `Day ${c.class_number}: ${formatCleanDate(c.scheduled_date)} | ${slotStr}`)
      .join("\n");

    return `*LEARN & DRIVE2*
*DIGITAL COURSE RECEIPT*
========================
*Receipt No:* ${data.receipt_no || "300"}
*Issue Date:* ${data.issue_date_formatted || formatShortDate(data.date)}

*CLIENT & COURSE DETAILS:*
• *Client Name:* ${data.student?.name || "—"}
• *Contact:* ${data.student?.phone || "—"}
• *Branch:* ${data.student?.location || data.school?.branch || "Khajaguda"}
• *Trainer:* ${trainerName} (${trainerPhone})
• *Course:* ${data.course_name || "Driving Training"}
• *Time Slot:* ${slotStr}
• *Start Date:* ${formatShortDate(data.student?.joining_date)}
• *Working Days:* Monday–Saturday
• *Daily Duration:* 1 hour
• *Validity:* ${data.validity || "12 calendar days"}
• *Sessions:* ${totalSessions} sessions

*TRAINING SCHEDULE:*
${scheduleLines}

*PAYMENT DETAILS:*
• *Course Fee:* ₹${(data.financials?.fees_total || 0).toLocaleString("en-IN")}
• *Amount Paid:* ₹${(data.financials?.fees_paid || 0).toLocaleString("en-IN")}
• *Balance:* ₹${(data.financials?.fees_balance || 0).toLocaleString("en-IN")}
• *Payment Mode:* ${data.payment_mode || "Cash"}
• *Status:* ${data.financials?.is_fully_paid ? "PAID IN FULL" : "BALANCE DUE"}
• *Received By:* ${data.received_by || "LEARN & DRIVE2"}

*Important Instructions:*
1. ${totalSessions} sessions, 1 hour daily; Monday–Saturday. Complete the course within 12 calendar days from joining.
2. Shoes are mandatory. Please arrive 5 minutes before your slot.
3. Carry valid Learner's License (LLR) during every session.

*THANK YOU FOR CHOOSING LEARN & DRIVE2!*
_LEARN • RIDE • DRIVE WITH CONFIDENCE_`;
  };

  const handleShareWhatsApp = (target, overridePhone = null) => {
    if (!data) return;
    const message = generateMessage();
    let rawPhone = overridePhone;

    if (!rawPhone) {
      if (target === "student") {
        rawPhone = data.student?.phone;
      } else if (target === "manager") {
        rawPhone = data.manager?.phone || "+918501852055";
      } else if (target === "trainer") {
        rawPhone = data.allotment?.assigned_trainer?.phone;
        if (!rawPhone || rawPhone === "—") {
          toast.error("Allotted trainer phone number is not available");
          return;
        }
      }
    }

    const clean = rawPhone?.replace(/[^0-9]/g, "");
    if (!clean) {
      toast.error(`Please provide a valid phone number`);
      return;
    }
    const targetPhone = clean.length === 10 ? `91${clean}` : clean;
    window.open(`https://wa.me/${targetPhone}?text=${encodeURIComponent(message)}`, "_blank");
  };

  const handleCopyText = () => {
    const message = generateMessage();
    navigator.clipboard.writeText(message);
    setCopied(true);
    toast.success("Receipt & Training Schedule copied to clipboard!");
    setTimeout(() => setCopied(false), 2000);
  };

  const student = data?.student || {};
  const allotment = data?.allotment || {};
  const schedule = data?.schedule || [];
  const financials = data?.financials || {};
  const totalSessions = data?.sessions_count || schedule.length || 10;
  const slotDisplay = formatSlotDisplay(allotment.slot_hour);
  const trainerName = allotment.assigned_trainer?.name || "Assigned Instructor";
  const trainerPhone = allotment.assigned_trainer?.phone || "—";
  const isPaidInFull = Boolean(financials.is_fully_paid);

  return (
    <div
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-start justify-center p-2 sm:p-4 md:p-6 pt-4 sm:pt-8 pb-16 overflow-y-auto"
    >
      <style>{`
        @media print {
          body * {
            visibility: hidden;
          }
          #printable-receipt, #printable-receipt * {
            visibility: visible;
          }
          #printable-receipt {
            position: absolute;
            left: 0;
            top: 0;
            width: 100% !important;
            max-width: 100% !important;
            margin: 0 !important;
            padding: 16px !important;
            background: #ffffff !important;
            color: #09090b !important;
            box-shadow: none !important;
            border: none !important;
          }
          .print-border-hairline {
            border-color: #e4e4e7 !important;
          }
          .print-bg-slate {
            background-color: #f8fafc !important;
          }
          .print-text-dark {
            color: #09090b !important;
          }
          .print-hide {
            display: none !important;
          }
          table {
            page-break-inside: auto;
          }
          tr {
            page-break-inside: avoid;
            page-break-after: auto;
          }
        }
      `}</style>

      <div className="w-full max-w-3xl bg-zinc-950 text-zinc-100 rounded-2xl border border-zinc-800 shadow-2xl overflow-hidden print:bg-white print:text-black print:border-none print:shadow-none print:rounded-none animate-in fade-in zoom-in-95 duration-150">
        
        {/* Top Control Bar (Hidden when printed) */}
        <div className="px-4 py-3 bg-zinc-900/95 border-b border-zinc-800/90 flex items-center justify-between gap-2.5 flex-wrap print:hidden">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
              <FileText size={18} weight="bold" />
            </div>
            <div>
              <div className="font-heading font-bold text-xs sm:text-sm tracking-wide uppercase text-zinc-100">
                Course Receipt &amp; Schedule
              </div>
              <div className="text-[11px] text-zinc-400 font-mono-data">
                {student.name ? `${student.name} • #${data?.receipt_no || "300"}` : "Learn & Drive 2"}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-1.5 flex-wrap">
            {/* WhatsApp to Student */}
            <button
              onClick={() => handleShareWhatsApp("student")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 active:scale-[0.97] text-white text-xs font-semibold rounded-lg transition-all duration-150 shadow-sm"
              title="Send to Student WhatsApp"
            >
              <WhatsappLogo size={15} weight="bold" /> WhatsApp
            </button>

            {/* WhatsApp to Trainer (if available) */}
            {trainerPhone && trainerPhone !== "—" && (
              <button
                onClick={() => handleShareWhatsApp("trainer")}
                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 active:scale-[0.97] text-xs font-medium rounded-lg transition-all duration-150"
                title="Send to Trainer WhatsApp"
              >
                <WhatsappLogo size={14} weight="bold" className="text-blue-400" /> Trainer
              </button>
            )}

            {/* Custom WhatsApp Number */}
            <button
              onClick={() => setShowCustomInput(!showCustomInput)}
              className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border transition-all duration-150 active:scale-[0.97] ${
                showCustomInput
                  ? "bg-amber-500/20 text-amber-300 border-amber-500/50"
                  : "bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border-zinc-700"
              }`}
              title="Send to specific WhatsApp Number"
            >
              <WhatsappLogo size={14} weight="bold" /> Custom No.
            </button>

            {/* Copy Receipt Text */}
            <button
              onClick={handleCopyText}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 active:scale-[0.97] text-xs font-medium rounded-lg transition-all duration-150"
              title="Copy receipt text to clipboard"
            >
              {copied ? (
                <>
                  <Check size={14} weight="bold" className="text-emerald-400" />
                  <span className="text-emerald-300 font-semibold">Copied</span>
                </>
              ) : (
                <>
                  <Copy size={14} weight="bold" />
                  <span>Copy</span>
                </>
              )}
            </button>

            {/* Print / Save as PDF */}
            <button
              onClick={handlePrint}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-amber-400 hover:bg-amber-300 active:scale-[0.97] text-zinc-950 text-xs font-bold rounded-lg transition-all duration-150 shadow-sm"
              title="Print Receipt / Save as PDF"
            >
              <Printer size={15} weight="bold" /> Print / PDF
            </button>

            {/* Close Modal Button */}
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 active:scale-95 transition-all duration-150 ml-1"
              title="Close (Esc)"
            >
              <X size={18} weight="bold" />
            </button>
          </div>
        </div>

        {/* Custom Phone Number Drawer */}
        {showCustomInput && (
          <div className="px-4 py-2.5 bg-zinc-900/70 border-b border-zinc-800 flex items-center gap-2 print:hidden animate-in slide-in-from-top-1 duration-150">
            <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider whitespace-nowrap">
              WhatsApp to:
            </span>
            <input
              type="tel"
              placeholder="e.g. 9876543210 (10 digits)"
              value={customPhone}
              autoFocus
              onChange={(e) => setCustomPhone(e.target.value)}
              className="flex-1 max-w-xs px-3 py-1.5 bg-zinc-950 border border-zinc-700 rounded-lg text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-amber-400 font-mono-data"
            />
            <button
              onClick={() => handleShareWhatsApp("custom", customPhone)}
              className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 active:scale-[0.97] text-white text-xs font-semibold rounded-lg inline-flex items-center gap-1.5 transition-all duration-150"
            >
              <PaperPlaneRight size={13} weight="bold" /> Send
            </button>
          </div>
        )}

        {loading ? (
          <div className="p-16 flex flex-col items-center justify-center gap-3 text-zinc-400">
            <div className="w-7 h-7 border-2 border-amber-400/30 border-t-amber-400 rounded-full animate-spin" />
            <div className="text-xs font-medium uppercase tracking-widest text-zinc-400">
              Generating Digital Course Receipt…
            </div>
          </div>
        ) : (
          /* Printable Course Receipt Document */
          <div
            id="printable-receipt"
            className="p-5 sm:p-8 font-sans bg-[#0c0e17] text-zinc-200 m-2 sm:m-4 rounded-xl border border-zinc-800/80 shadow-inner print:p-0 print:m-0 print:border-none print:bg-white print:text-zinc-950"
          >
            {/* Top Micro-Accent Band (Hidden in print) */}
            <div className="h-0.5 w-full bg-gradient-to-r from-transparent via-amber-400/60 to-transparent mb-5 print-hide" />

            {/* Header / Academy Crest */}
            <div className="flex flex-col items-center justify-center text-center pb-4 border-b border-zinc-800/80 print:border-zinc-300">
              
              {/* Refined Vector Emblem */}
              <div className="mb-2.5 flex items-center justify-center">
                <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-amber-400/20 to-amber-600/10 border border-amber-400/40 flex items-center justify-center text-amber-400 shadow-sm print:bg-zinc-100 print:border-zinc-800 print:text-zinc-950">
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="w-6 h-6"
                  >
                    <circle cx="12" cy="12" r="9" />
                    <circle cx="12" cy="12" r="3" />
                    <path d="M12 3v6" />
                    <path d="M12 15v6" />
                    <path d="M3 12h6" />
                    <path d="M15 12h6" />
                  </svg>
                </div>
              </div>

              <div className="text-[10px] font-bold tracking-[0.28em] uppercase text-amber-400 print:text-zinc-700 mb-0.5">
                GOVT. REGISTERED MOTOR DRIVING ACADEMY
              </div>
              <h1 className="font-heading text-2xl sm:text-3xl font-black tracking-tight text-white uppercase print:text-zinc-950">
                LEARN &amp; DRIVE2
              </h1>
              <div className="text-xs font-semibold tracking-wider uppercase text-zinc-400 mt-0.5 print:text-zinc-600">
                DIGITAL COURSE RECEIPT &amp; TRAINING SCHEDULE
              </div>
              <div className="text-[11px] text-zinc-400 font-mono-data mt-1 print:text-zinc-600">
                Branch: {data?.school?.branch || student.location || "Khajaguda"} • Contact: +91 85018 52055
              </div>
            </div>

            {/* Receipt Metadata Ribbon (Receipt No, Date, Payment Status) */}
            <div className="my-4 grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs font-mono-data">
              <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-lg p-2.5 flex flex-col justify-center print:bg-zinc-50 print:border-zinc-300">
                <span className="text-[10px] uppercase font-bold text-zinc-400 print:text-zinc-600 tracking-wider">
                  Receipt Number
                </span>
                <span className="font-bold text-white text-sm print:text-zinc-950">
                  #{data.receipt_no || "300"}
                </span>
              </div>

              <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-lg p-2.5 flex flex-col justify-center print:bg-zinc-50 print:border-zinc-300">
                <span className="text-[10px] uppercase font-bold text-zinc-400 print:text-zinc-600 tracking-wider">
                  Issue Date
                </span>
                <span className="font-bold text-white text-sm print:text-zinc-950">
                  {data.issue_date_formatted || formatShortDate(data.date)}
                </span>
              </div>

              <div
                className={`border rounded-lg p-2.5 flex flex-col justify-center ${
                  isPaidInFull
                    ? "bg-emerald-950/20 border-emerald-500/30 text-emerald-400 print:bg-emerald-50 print:border-emerald-300 print:text-emerald-800"
                    : "bg-amber-950/20 border-amber-500/30 text-amber-300 print:bg-amber-50 print:border-amber-300 print:text-amber-800"
                }`}
              >
                <span className="text-[10px] uppercase font-bold tracking-wider opacity-80">
                  Enrollment Status
                </span>
                <div className="flex items-center gap-1.5 font-bold text-sm">
                  {isPaidInFull ? (
                    <>
                      <CheckCircle size={15} weight="bold" />
                      <span>PAID IN FULL</span>
                    </>
                  ) : (
                    <>
                      <Clock size={15} weight="bold" />
                      <span>BALANCE DUE: ₹{(financials.fees_balance || 0).toLocaleString("en-IN")}</span>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* SECTION 1: CLIENT & COURSE DETAILS */}
            <div className="mb-4">
              <div className="text-[11px] font-bold tracking-wider uppercase text-amber-400 mb-2 flex items-center gap-1.5 print:text-zinc-900">
                <User size={13} weight="bold" />
                <span>Client &amp; Course Credentials</span>
              </div>
              <div className="border border-zinc-800/80 rounded-xl overflow-hidden text-xs bg-zinc-900/30 print:border-zinc-300 print:bg-white print:rounded-none">
                <table className="w-full border-collapse">
                  <tbody className="divide-y divide-zinc-800/60 print:divide-zinc-200">
                    <tr className="divide-x divide-zinc-800/60 print:divide-zinc-200">
                      <td className="p-2.5 w-1/4 font-semibold text-zinc-400 bg-zinc-900/40 print:bg-zinc-50 print:text-zinc-700">
                        Client Name
                      </td>
                      <td className="p-2.5 w-1/4 font-bold text-white print:text-zinc-950">
                        {student.name || "—"}
                      </td>
                      <td className="p-2.5 w-1/4 font-semibold text-zinc-400 bg-zinc-900/40 print:bg-zinc-50 print:text-zinc-700">
                        Age
                      </td>
                      <td className="p-2.5 w-1/4 text-zinc-300 print:text-zinc-900 font-mono-data">
                        {student.age || "—"}
                      </td>
                    </tr>
                    <tr className="divide-x divide-zinc-800/60 print:divide-zinc-200">
                      <td className="p-2.5 font-semibold text-zinc-400 bg-zinc-900/40 print:bg-zinc-50 print:text-zinc-700">
                        Contact No.
                      </td>
                      <td className="p-2.5 font-mono-data font-bold text-white print:text-zinc-950">
                        {student.phone || "—"}
                      </td>
                      <td className="p-2.5 font-semibold text-zinc-400 bg-zinc-900/40 print:bg-zinc-50 print:text-zinc-700">
                        Branch
                      </td>
                      <td className="p-2.5 font-bold text-white print:text-zinc-950">
                        {student.location || data.school?.branch || "Khajaguda"}
                      </td>
                    </tr>
                    <tr className="divide-x divide-zinc-800/60 print:divide-zinc-200">
                      <td className="p-2.5 font-semibold text-zinc-400 bg-zinc-900/40 print:bg-zinc-50 print:text-zinc-700">
                        Assigned Trainer
                      </td>
                      <td className="p-2.5 font-bold text-white print:text-zinc-950">
                        {trainerName}
                        {trainerPhone && trainerPhone !== "—" && (
                          <span className="block text-[11px] font-mono-data text-zinc-400 print:text-zinc-600 font-normal">
                            ({trainerPhone})
                          </span>
                        )}
                      </td>
                      <td className="p-2.5 font-semibold text-zinc-400 bg-zinc-900/40 print:bg-zinc-50 print:text-zinc-700">
                        Course
                      </td>
                      <td className="p-2.5 font-bold text-white print:text-zinc-950">
                        {data.course_name || "Scooty Training"}
                      </td>
                    </tr>
                    <tr className="divide-x divide-zinc-800/60 print:divide-zinc-200">
                      <td className="p-2.5 font-semibold text-zinc-400 bg-zinc-900/40 print:bg-zinc-50 print:text-zinc-700">
                        Time Slot
                      </td>
                      <td className="p-2.5 font-mono-data font-bold text-amber-300 print:text-zinc-950">
                        {slotDisplay}
                      </td>
                      <td className="p-2.5 font-semibold text-zinc-400 bg-zinc-900/40 print:bg-zinc-50 print:text-zinc-700">
                        Start Date
                      </td>
                      <td className="p-2.5 font-mono-data font-bold text-white print:text-zinc-950">
                        {formatShortDate(student.joining_date)}
                      </td>
                    </tr>
                    <tr className="divide-x divide-zinc-800/60 print:divide-zinc-200">
                      <td className="p-2.5 font-semibold text-zinc-400 bg-zinc-900/40 print:bg-zinc-50 print:text-zinc-700">
                        Working Days
                      </td>
                      <td className="p-2.5 text-zinc-200 print:text-zinc-900">
                        Monday – Saturday
                      </td>
                      <td className="p-2.5 font-semibold text-zinc-400 bg-zinc-900/40 print:bg-zinc-50 print:text-zinc-700">
                        Daily Duration
                      </td>
                      <td className="p-2.5 text-zinc-200 print:text-zinc-900">
                        1 hour daily
                      </td>
                    </tr>
                    <tr className="divide-x divide-zinc-800/60 print:divide-zinc-200">
                      <td className="p-2.5 font-semibold text-zinc-400 bg-zinc-900/40 print:bg-zinc-50 print:text-zinc-700">
                        Course Validity
                      </td>
                      <td className="p-2.5 font-mono-data text-zinc-200 print:text-zinc-900">
                        {data.validity || "12 calendar days"}
                      </td>
                      <td className="p-2.5 font-semibold text-zinc-400 bg-zinc-900/40 print:bg-zinc-50 print:text-zinc-700">
                        Total Sessions
                      </td>
                      <td className="p-2.5 font-bold text-amber-300 print:text-zinc-950 font-mono-data">
                        {totalSessions} Sessions
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            {/* SECTION 2: TRAINING SCHEDULE MATRIX */}
            <div className="mb-4">
              <div className="text-[11px] font-bold tracking-wider uppercase text-amber-400 mb-2 flex items-center justify-between print:text-zinc-900">
                <span className="flex items-center gap-1.5">
                  <CalendarBlank size={13} weight="bold" />
                  <span>Training Schedule — {totalSessions} Daily Sessions</span>
                </span>
                <span className="text-[10px] font-mono-data text-zinc-400 print:text-zinc-600 font-normal">
                  Mon–Sat • 1 hr/day
                </span>
              </div>
              <div className="border border-zinc-800/80 rounded-xl overflow-hidden text-xs bg-zinc-900/20 print:border-zinc-300 print:bg-white print:rounded-none">
                <table className="w-full border-collapse">
                  <thead className="bg-zinc-900/80 border-b border-zinc-800 text-zinc-300 font-semibold uppercase text-[10px] tracking-wider print:bg-zinc-100 print:text-zinc-900 print:border-zinc-300">
                    <tr>
                      <th className="py-2 px-3 text-left w-14">Day</th>
                      <th className="py-2 px-3 text-left">Date</th>
                      <th className="py-2 px-3 text-left">Assigned Slot</th>
                      <th className="py-2 px-3 text-right">Session Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/50 font-mono-data print:divide-zinc-200">
                    {schedule.slice(0, totalSessions).map((c) => (
                      <tr
                        key={c.class_number}
                        className="hover:bg-zinc-900/40 transition-colors print:hover:bg-transparent"
                      >
                        <td className="py-1.5 px-3 font-bold text-amber-400 print:text-zinc-900">
                          <span className="inline-block px-1.5 py-0.5 rounded bg-zinc-800/80 text-[11px] print:bg-zinc-200">
                            {String(c.class_number).padStart(2, "0")}
                          </span>
                        </td>
                        <td className="py-1.5 px-3 text-zinc-200 print:text-zinc-900 font-medium">
                          {formatCleanDate(c.scheduled_date)}
                        </td>
                        <td className="py-1.5 px-3 text-zinc-300 print:text-zinc-700">
                          {slotDisplay}
                        </td>
                        <td className="py-1.5 px-3 text-right">
                          <span
                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider ${
                              c.status === "completed"
                                ? "bg-emerald-950/40 text-emerald-400 border border-emerald-500/30 print:bg-transparent print:text-emerald-700 print:border-none"
                                : c.status === "missed"
                                ? "bg-rose-950/40 text-rose-400 border border-rose-500/30 print:bg-transparent print:text-rose-700 print:border-none"
                                : "bg-zinc-800/60 text-zinc-400 border border-zinc-700/50 print:bg-transparent print:text-zinc-600 print:border-none"
                            }`}
                          >
                            <span
                              className={`w-1.5 h-1.5 rounded-full ${
                                c.status === "completed"
                                  ? "bg-emerald-400"
                                  : c.status === "missed"
                                  ? "bg-rose-400"
                                  : "bg-zinc-500"
                              }`}
                            />
                            {c.status === "completed" ? "Completed" : c.status === "missed" ? "Missed" : "Scheduled"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* SECTION 3: PAYMENT LEDGER */}
            <div className="mb-4">
              <div className="text-[11px] font-bold tracking-wider uppercase text-amber-400 mb-2 flex items-center gap-1.5 print:text-zinc-900">
                <CurrencyInr size={13} weight="bold" />
                <span>Payment Summary &amp; Financial Ledger</span>
              </div>
              <div className="border border-zinc-800/80 rounded-xl overflow-hidden text-xs bg-zinc-900/30 print:border-zinc-300 print:bg-white print:rounded-none">
                <table className="w-full border-collapse">
                  <tbody className="divide-y divide-zinc-800/60 print:divide-zinc-200">
                    <tr className="divide-x divide-zinc-800/60 print:divide-zinc-200">
                      <td className="p-2.5 font-semibold text-zinc-400 bg-zinc-900/40 print:bg-zinc-50 print:text-zinc-700">
                        Course Fee
                      </td>
                      <td className="p-2.5 font-mono-data font-bold text-white text-sm print:text-zinc-950">
                        ₹{(financials.fees_total || 0).toLocaleString("en-IN")}
                      </td>
                      <td className="p-2.5 font-semibold text-zinc-400 bg-zinc-900/40 print:bg-zinc-50 print:text-zinc-700">
                        Amount Paid
                      </td>
                      <td className="p-2.5 font-mono-data font-bold text-emerald-400 text-sm print:text-emerald-700">
                        ₹{(financials.fees_paid || 0).toLocaleString("en-IN")}
                      </td>
                      <td className="p-2.5 font-semibold text-zinc-400 bg-zinc-900/40 print:bg-zinc-50 print:text-zinc-700">
                        Balance Due
                      </td>
                      <td
                        className={`p-2.5 font-mono-data font-bold text-sm ${
                          financials.fees_balance > 0
                            ? "text-amber-300 print:text-amber-800"
                            : "text-zinc-400 print:text-zinc-700"
                        }`}
                      >
                        ₹{(financials.fees_balance || 0).toLocaleString("en-IN")}
                      </td>
                    </tr>
                    <tr className="divide-x divide-zinc-800/60 print:divide-zinc-200">
                      <td className="p-2.5 font-semibold text-zinc-400 bg-zinc-900/40 print:bg-zinc-50 print:text-zinc-700">
                        Payment Mode
                      </td>
                      <td className="p-2.5 font-bold text-white print:text-zinc-950">
                        {data.payment_mode || "Cash"}
                      </td>
                      <td className="p-2.5 font-semibold text-zinc-400 bg-zinc-900/40 print:bg-zinc-50 print:text-zinc-700">
                        Payment Status
                      </td>
                      <td className="p-2.5 font-bold print:text-zinc-950">
                        {isPaidInFull ? (
                          <span className="text-emerald-400 print:text-emerald-700">PAID IN FULL</span>
                        ) : (
                          <span className="text-amber-300 print:text-amber-700">BALANCE DUE</span>
                        )}
                      </td>
                      <td className="p-2.5 font-semibold text-zinc-400 bg-zinc-900/40 print:bg-zinc-50 print:text-zinc-700">
                        Received By
                      </td>
                      <td className="p-2.5 font-bold text-amber-400 print:text-zinc-950">
                        {data.received_by || "LEARN & DRIVE2"}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            {/* Terms & Important Instructions */}
            <div className="p-3 bg-zinc-900/40 border border-zinc-800/60 rounded-xl text-[11px] text-zinc-400 space-y-1.5 mb-5 leading-relaxed print:bg-zinc-50 print:border-zinc-300 print:text-zinc-800 print:rounded-none">
              <div className="font-bold text-zinc-300 print:text-zinc-900 uppercase tracking-wider text-[10px]">
                Important Course Terms:
              </div>
              <ul className="list-disc pl-4 space-y-1">
                <li>
                  <strong className="text-zinc-200 print:text-zinc-900">{totalSessions} sessions</strong>, 1 hour daily, Monday through Saturday. Complete all sessions within <strong>12 calendar days</strong> from the start date.
                </li>
                <li>
                  Shoes are <strong>mandatory</strong> during driving sessions. Please arrive at your allotted branch 5 minutes prior to your time slot.
                </li>
                <li>
                  Learner's License (LLR) must be carried during every driving session as mandated by the Transport Department.
                </li>
              </ul>
            </div>

            {/* Official Signature & Bottom Seal */}
            <div className="pt-3 border-t border-zinc-800/80 flex flex-col sm:flex-row items-center justify-between gap-3 text-center sm:text-left print:border-zinc-300">
              <div className="space-y-0.5">
                <div className="font-heading font-black text-xs sm:text-sm tracking-wider uppercase text-amber-400 print:text-zinc-950">
                  LEARN &amp; DRIVE2 MOTOR DRIVING ACADEMY
                </div>
                <div className="text-[10px] font-bold tracking-[0.2em] uppercase text-zinc-500 print:text-zinc-600">
                  LEARN • RIDE • DRIVE WITH CONFIDENCE
                </div>
              </div>

              {/* Digital Authorized Seal */}
              <div className="flex items-center gap-2 border border-emerald-500/30 bg-emerald-950/20 px-3 py-1.5 rounded-lg text-emerald-400 print:border-zinc-400 print:bg-zinc-50 print:text-zinc-800">
                <ShieldCheck size={18} weight="bold" />
                <div className="text-[10px] font-mono-data font-bold uppercase tracking-wider">
                  Digitally Verified Receipt
                </div>
              </div>
            </div>

          </div>
        )}
      </div>
    </div>
  );
}
