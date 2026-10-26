import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import {
  Printer,
  WhatsappLogo,
  FileText,
  Copy,
  Check,
  PaperPlaneRight,
  ShieldCheck,
  CalendarBlank,
  Clock,
  User,
  CurrencyInr,
  CheckCircle,
  ArrowLeft,
} from "@phosphor-icons/react";
import { toast } from "sonner";

export default function InvoicePage() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [customPhone, setCustomPhone] = useState("");
  const [showCustomInput, setShowCustomInput] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (id) {
      setLoading(true);
      api
        .get(`/students/${id}/invoice`)
        .then((res) => {
          setData(res.data);
          setError(null);
        })
        .catch((err) => {
          const msg = formatApiError(err.response?.data?.detail) || "Failed to load invoice";
          setError(msg);
          toast.error(msg);
        })
        .finally(() => setLoading(false));
    }
  }, [id]);

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
        const h12 = h % 12 || 12;
        return { str: `${h12}:00`, ampm };
      };
      const t1 = toHour(parts[0]);
      const t2 = toHour(parts[1]);
      if (t1.ampm === t2.ampm) {
        return `${t1.str} - ${t2.str} ${t2.ampm}`;
      }
      return `${t1.str} ${t1.ampm} - ${t2.str} ${t2.ampm}`;
    }
    return s;
  };

  const generateMessage = () => {
    if (!data) return "";
    const trainerName = data.allotment?.assigned_trainer?.name || "Assigned Instructor";
    const trainerPhone = data.allotment?.assigned_trainer?.phone || "Branch";
    const totalSessions = data.sessions_count || data.schedule?.length || 10;
    const slotStr = formatSlotDisplay(data.allotment?.slot_hour);

    const scheduleLines = (data.schedule || [])
      .slice(0, totalSessions)
      .map((c) => `  Day ${String(c.class_number).padStart(2, "0")}: ${formatCleanDate(c.scheduled_date)} (${slotStr})`)
      .join("\n");

    return `🚗 *LEARN & DRIVE 2 MOTOR DRIVING ACADEMY*
*Official Admission Slip & Training Schedule*
----------------------------------------
*Receipt No:* #${data.receipt_no || "300"}
*Issue Date:* ${data.issue_date_formatted || formatShortDate(data.date)}

*STUDENT & COURSE DETAILS:*
• *Client Name:* ${data.student?.name || "—"}
• *Contact:* ${data.student?.phone || "—"}
• *Branch:* ${data.student?.location || data.school?.branch || "Khajaguda"}
• *Trainer:* ${trainerName} (${trainerPhone})
• *Course:* ${data.course_name || "Driving Training"}
• *Time Slot:* ${slotStr}
• *Start Date:* ${formatShortDate(data.student?.joining_date)}
• *Working Days:* Monday–Saturday
• *Daily Duration:* 1 hour
• *Validity:* ${data.validity || "10 calendar days"}
• *Sessions:* ${totalSessions} sessions

*TRAINING SCHEDULE:*
${scheduleLines}

*PAYMENT DETAILS:*
• *Course Fee:* ₹${(data.financials?.fees_total || 0).toLocaleString("en-IN")}
• *Amount Paid:* ₹${(data.financials?.fees_paid || 0).toLocaleString("en-IN")}
• *Balance:* ₹${(data.financials?.fees_balance || 0).toLocaleString("en-IN")}
• *Payment Mode:* ${data.payment_mode || "Cash"}
• *Status:* ${data.financials?.is_fully_paid ? "PAID IN FULL" : "BALANCE DUE"}
• *Received By:* ${data.received_by || "LEARN & DRIVE 2"}

*Important Instructions:*
1. ${totalSessions} sessions, 1 hour daily; Monday–Saturday. Complete the course within 10 calendar days from joining.
2. Shoes are mandatory. Please arrive 5 minutes before your slot.
3. Carry valid Learner's License (LLR) during every session.

*THANK YOU FOR CHOOSING LEARN & DRIVE 2!*
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
    const isMobile = typeof navigator !== "undefined" && /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
    const waUrl = isMobile
      ? `https://api.whatsapp.com/send?phone=${targetPhone}&text=${encodeURIComponent(message)}`
      : `https://web.whatsapp.com/send?phone=${targetPhone}&text=${encodeURIComponent(message)}`;
    window.open(waUrl, "_blank", "noopener,noreferrer");
  };

  const handleCopyText = () => {
    const message = generateMessage();
    navigator.clipboard.writeText(message);
    setCopied(true);
    toast.success("Receipt & Training Schedule copied to clipboard!");
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center gap-3 text-zinc-400">
        <div className="w-8 h-8 border-2 border-amber-400/30 border-t-amber-400 rounded-full animate-spin" />
        <div className="text-xs font-medium uppercase tracking-widest text-zinc-400">
          Loading Course Receipt…
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center p-4 text-center">
        <div className="w-12 h-12 rounded-xl bg-red-950/40 border border-red-500/30 flex items-center justify-center text-red-400 mb-3">
          <FileText size={24} weight="bold" />
        </div>
        <h2 className="text-lg font-bold text-white mb-1">Unable to Load Receipt</h2>
        <p className="text-xs text-zinc-400 max-w-sm mb-6">{error || "Student receipt could not be found."}</p>
        <Link
          to="/students"
          className="inline-flex items-center gap-1.5 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-white text-xs font-semibold rounded-lg transition-colors"
        >
          <ArrowLeft size={14} weight="bold" /> Back to Students
        </Link>
      </div>
    );
  }

  const student = data.student || {};
  const allotment = data.allotment || {};
  const schedule = data.schedule || [];
  const financials = data.financials || {};
  const totalSessions = data.sessions_count || schedule.length || 10;
  const slotDisplay = formatSlotDisplay(allotment.slot_hour);
  const trainerName = allotment.assigned_trainer?.name || "Assigned Instructor";
  const trainerPhone = allotment.assigned_trainer?.phone || "—";
  const isPaidInFull = Boolean(financials.is_fully_paid);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col items-center py-4 px-2 sm:px-6 print:bg-white print:p-0 print:m-0 print:min-h-0">
      <style>{`
        @media print {
          @page {
            size: A4 portrait;
            margin: 6mm 8mm;
          }
          html, body {
            margin: 0 !important;
            padding: 0 !important;
            height: auto !important;
            min-height: 0 !important;
            background: #ffffff !important;
            color: #09090b !important;
            overflow: visible !important;
          }
          .print-hide, .print\\:hidden {
            display: none !important;
          }
          #printable-receipt {
            margin: 0 !important;
            padding: 0 !important;
            width: 100% !important;
            max-width: 100% !important;
            background: #ffffff !important;
            color: #09090b !important;
            box-shadow: none !important;
            border: none !important;
            page-break-inside: avoid !important;
            break-inside: avoid !important;
          }
          #printable-receipt * {
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
          }
          #printable-receipt table {
            width: 100% !important;
            border-collapse: collapse !important;
            page-break-inside: avoid !important;
            break-inside: avoid !important;
          }
          #printable-receipt tr {
            page-break-inside: avoid !important;
            break-inside: avoid !important;
          }
          #printable-receipt td,
          #printable-receipt th {
            padding: 2.5px 6px !important;
            font-size: 10px !important;
            line-height: 1.25 !important;
          }
          #printable-receipt h1 {
            font-size: 19px !important;
            line-height: 1.15 !important;
            margin: 1px 0 !important;
          }
          #printable-receipt .receipt-header {
            padding-bottom: 4px !important;
            margin-bottom: 4px !important;
          }
          #printable-receipt .receipt-ribbon {
            margin-top: 5px !important;
            margin-bottom: 6px !important;
            gap: 5px !important;
          }
          #printable-receipt .receipt-ribbon > div {
            padding: 3px 6px !important;
          }
          #printable-receipt .section-block {
            margin-bottom: 6px !important;
          }
          #printable-receipt .section-heading {
            margin-bottom: 2px !important;
            font-size: 9.5px !important;
          }
          #printable-receipt .terms-block {
            padding: 5px 8px !important;
            margin-bottom: 6px !important;
            font-size: 9px !important;
            line-height: 1.3 !important;
          }
          #printable-receipt .terms-block ul {
            margin-top: 2px !important;
          }
          #printable-receipt .footer-block {
            padding-top: 4px !important;
          }
        }
      `}</style>

      {/* Top Floating Control Bar (Hidden when printed) */}
      <div className="w-full max-w-3xl mb-4 bg-zinc-900/90 border border-zinc-800 rounded-xl p-3 flex items-center justify-between gap-3 flex-wrap print:hidden backdrop-blur-md shadow-lg">
        <div className="flex items-center gap-2">
          <Link
            to={`/students/${id}`}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 active:scale-95 transition-all"
            title="Back to Student Profile"
          >
            <ArrowLeft size={16} weight="bold" />
          </Link>
          <div>
            <div className="font-heading font-bold text-xs sm:text-sm tracking-wide uppercase text-zinc-100">
              Course Receipt #{data.receipt_no || "300"}
            </div>
            <div className="text-[11px] text-zinc-400 font-mono-data">
              {student.name || "Learn & Drive 2"}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1.5 flex-wrap">
          {/* WhatsApp to Student */}
          <button
            onClick={() => handleShareWhatsApp("student")}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 active:scale-[0.97] text-white text-xs font-semibold rounded-lg transition-all shadow-sm"
            title="Send to Student WhatsApp"
          >
            <WhatsappLogo size={15} weight="bold" /> WhatsApp
          </button>

          {/* WhatsApp to Trainer */}
          {trainerPhone && trainerPhone !== "—" && (
            <button
              onClick={() => handleShareWhatsApp("trainer")}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 active:scale-[0.97] text-xs font-medium rounded-lg transition-all"
              title="Send to Trainer WhatsApp"
            >
              <WhatsappLogo size={14} weight="bold" className="text-blue-400" /> Trainer
            </button>
          )}

          {/* Custom WhatsApp Number */}
          <button
            onClick={() => setShowCustomInput(!showCustomInput)}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border transition-all active:scale-[0.97] ${
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
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 active:scale-[0.97] text-xs font-medium rounded-lg transition-all"
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
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-amber-400 hover:bg-amber-300 active:scale-[0.97] text-zinc-950 text-xs font-bold rounded-lg transition-all shadow-sm"
            title="Print Receipt / Save as PDF"
          >
            <Printer size={15} weight="bold" /> Print / PDF
          </button>
        </div>
      </div>

      {/* Custom Phone Number Drawer */}
      {showCustomInput && (
        <div className="w-full max-w-3xl mb-4 px-4 py-2.5 bg-zinc-900 border border-zinc-800 rounded-xl flex items-center gap-2 print:hidden animate-in slide-in-from-top-1 duration-150">
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
            className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 active:scale-[0.97] text-white text-xs font-semibold rounded-lg inline-flex items-center gap-1.5 transition-all"
          >
            <PaperPlaneRight size={13} weight="bold" /> Send
          </button>
        </div>
      )}

      {/* Printable Course Receipt Document */}
      <div
        id="printable-receipt"
        className="w-full max-w-3xl p-5 sm:p-8 font-sans bg-[#0c0e17] text-zinc-200 rounded-2xl border border-zinc-800 shadow-2xl print:p-0 print:m-0 print:border-none print:bg-white print:text-zinc-950 print:rounded-none print:shadow-none"
      >
        {/* Top Micro-Accent Band (Hidden in print) */}
        <div className="h-0.5 w-full bg-gradient-to-r from-transparent via-amber-400/60 to-transparent mb-5 print-hide" />

        {/* Header / Academy Crest */}
        <div className="receipt-header flex flex-col items-center justify-center text-center pb-4 border-b border-zinc-800/80 print:border-zinc-300">
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
            LEARN &amp; DRIVE 2
          </h1>
          <div className="text-xs font-semibold tracking-wider uppercase text-zinc-400 mt-0.5 print:text-zinc-600">
            DIGITAL COURSE RECEIPT &amp; TRAINING SCHEDULE
          </div>
          <div className="text-[11px] text-zinc-400 font-mono-data mt-1 print:text-zinc-600">
            Branch: {data.school?.branch || student.location || "Khajaguda"} • Contact: +91 85018 52055
          </div>
        </div>

        {/* Receipt Metadata Ribbon (Receipt No, Date, Payment Status) */}
        <div className="receipt-ribbon my-4 grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs font-mono-data">
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
        <div className="section-block mb-4">
          <div className="section-heading text-[11px] font-bold tracking-wider uppercase text-amber-400 mb-2 flex items-center gap-1.5 print:text-zinc-900">
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
                    {data.validity || "10 calendar days"}
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
        <div className="section-block mb-4">
          <div className="section-heading text-[11px] font-bold tracking-wider uppercase text-amber-400 mb-2 flex items-center justify-between print:text-zinc-900">
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
                            : (c.status === "absent" || c.status === "missed")
                            ? "bg-rose-950/40 text-rose-400 border border-rose-500/30 print:bg-transparent print:text-rose-700 print:border-none"
                            : "bg-zinc-800/60 text-zinc-400 border border-zinc-700/50 print:bg-transparent print:text-zinc-600 print:border-none"
                        }`}
                      >
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${
                            c.status === "completed"
                              ? "bg-emerald-400"
                              : (c.status === "absent" || c.status === "missed")
                              ? "bg-rose-400"
                              : "bg-zinc-500"
                          }`}
                        />
                        {c.status === "completed" ? "Completed" : (c.status === "absent" || c.status === "missed") ? "Absent" : "Scheduled"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* SECTION 3: PAYMENT LEDGER */}
        <div className="section-block mb-4">
          <div className="section-heading text-[11px] font-bold tracking-wider uppercase text-amber-400 mb-2 flex items-center gap-1.5 print:text-zinc-900">
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
                    {data.received_by || "LEARN & DRIVE 2"}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* Terms & Important Instructions */}
        <div className="terms-block p-3 bg-zinc-900/40 border border-zinc-800/60 rounded-xl text-[11px] text-zinc-400 space-y-1.5 mb-5 leading-relaxed print:bg-zinc-50 print:border-zinc-300 print:text-zinc-800 print:rounded-none">
          <div className="font-bold text-zinc-300 print:text-zinc-900 uppercase tracking-wider text-[10px]">
            Important Course Terms:
          </div>
          <ul className="list-disc pl-4 space-y-1">
            <li>
              <strong className="text-zinc-200 print:text-zinc-900">{totalSessions} sessions</strong>, 1 hour daily, Monday through Saturday. Complete all sessions within <strong>10 calendar days</strong> from the start date.
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
        <div className="footer-block pt-3 border-t border-zinc-800/80 flex flex-col sm:flex-row items-center justify-between gap-3 text-center sm:text-left print:border-zinc-300">
          <div className="space-y-0.5">
            <div className="font-heading font-black text-xs sm:text-sm tracking-wider uppercase text-amber-400 print:text-zinc-950">
              LEARN &amp; DRIVE 2 MOTOR DRIVING ACADEMY
            </div>
            <div className="text-[10px] font-bold tracking-[0.2em] uppercase text-zinc-500 print:text-zinc-600">
              LEARN • RIDE • DRIVE WITH CONFIDENCE
            </div>
          </div>

          <div className="flex items-center gap-2 border border-emerald-500/30 bg-emerald-950/20 px-3 py-1.5 rounded-lg text-emerald-400 print:border-zinc-400 print:bg-zinc-50 print:text-zinc-800">
            <ShieldCheck size={18} weight="bold" />
            <div className="text-[10px] font-mono-data font-bold uppercase tracking-wider">
              Digitally Verified Receipt
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
