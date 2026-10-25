import React, { useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { formatSlot12 } from "@/lib/utils";
import {
  Printer,
  WhatsappLogo,
  X,
  CheckCircle,
  Clock,
  User,
  ShieldCheck,
  FileText,
  MapPin,
  Phone,
  Copy,
} from "@phosphor-icons/react";
import { toast } from "sonner";

export default function InvoiceModal({ studentId, open, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

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

  if (!open) return null;

  const handlePrint = () => {
    window.print();
  };

  const generateMessage = () => {
    if (!data) return "";
    const trainerInfo = data.allotment?.assigned_trainer?.name
      ? `${data.allotment.assigned_trainer.name} (${data.allotment.assigned_trainer.phone || "Branch"})`
      : "Assigned at Branch";

    const scheduleList = (data.schedule || [])
      .slice(0, 12)
      .map((c) => `• Class ${c.class_number}: ${c.scheduled_date || "TBD"}`)
      .join("\n");

    return `*RIDEWELL MOTOR DRIVING SCHOOL*
*Official Admission Slip & Training Invoice*
----------------------------------------
*Invoice No:* ${data.invoice_number}
*Student:* ${data.student?.name}
*Phone:* ${data.student?.phone}
*Branch:* ${data.school?.branch}
*Course:* 12 Working Days Training (${data.student?.license_type?.toUpperCase()})

*TRAINING ALLOTMENT:*
• *Allotted Slot Time:* ${formatSlot12(data.allotment?.slot_hour)}
• *Allotted Instructor:* ${trainerInfo}
${data.student?.needs_pickup ? `• *Pickup Address:* ${data.student.pickup_address || "Provided"}\n` : ""}
*12 WORKING DAYS SCHEDULE:*
${scheduleList}

*FEE RECEIPT:*
• *Total Fees:* ₹${data.financials?.fees_total?.toLocaleString("en-IN")}
• *Fees Paid:* ₹${data.financials?.fees_paid?.toLocaleString("en-IN")}
• *Balance Due:* ₹${data.financials?.fees_balance?.toLocaleString("en-IN")}
• *Status:* ${data.financials?.status_label}

*MANDATORY INSTRUCTIONS:*
1. Arrive strictly at your allotted time slot (${formatSlot12(data.allotment?.slot_hour)}).
2. Always carry your valid Learner's License (LLR) copy.
3. Wear flat footwear/sneakers during training.
4. Advance 12h notice required for emergency rescheduling.

For queries, contact your branch: ${data.school?.phone}`;
  };

  const handleShareWhatsApp = (target) => {
    if (!data) return;
    const message = generateMessage();
    let rawPhone = "";
    if (target === "student") {
      rawPhone = data.student?.phone;
    } else if (target === "manager") {
      rawPhone = data.manager?.phone || "+91 98765 43211";
    } else if (target === "trainer") {
      rawPhone = data.allotment?.assigned_trainer?.phone;
      if (!rawPhone) {
        toast.error("Allotted trainer phone number not available");
        return;
      }
    }

    const clean = rawPhone?.replace(/[^0-9]/g, "");
    if (!clean) {
      toast.error(`Phone number for ${target} not available`);
      return;
    }
    const targetPhone = clean.length === 10 ? `91${clean}` : clean;
    window.open(`https://wa.me/${targetPhone}?text=${encodeURIComponent(message)}`, "_blank");
  };

  const handleCopyText = () => {
    const message = generateMessage();
    navigator.clipboard.writeText(message);
    toast.success("Admission Slip & Schedule copied to clipboard!");
  };

  const school = data?.school || {};
  const student = data?.student || {};
  const allotment = data?.allotment || {};
  const schedule = data?.schedule || [];
  const financials = data?.financials || {};
  const instructions = data?.instructions || [];
  const manager = data?.manager || {};

  return (
    <div className="fixed inset-0 z-50 bg-zinc-900/70 backdrop-blur-xs flex items-start justify-center p-4 pt-8 pb-12 overflow-y-auto">
      <div className="bg-white border-2 border-zinc-900 w-full max-w-3xl shadow-2xl animate-in fade-in zoom-in-95">
        {/* Action Top Bar (Hidden during print) */}
        <div className="p-4 border-b border-zinc-200 flex items-center justify-between gap-3 bg-zinc-50 print:hidden flex-wrap">
          <div className="flex items-center gap-2">
            <FileText size={18} weight="bold" className="text-zinc-800" />
            <span className="font-heading font-black text-sm uppercase tracking-wider">
              Admission Slip &amp; Course Invoice
            </span>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => handleShareWhatsApp("manager")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold uppercase tracking-wider transition-colors shadow-sm"
              title={`Send invoice & 12-day schedule to ${manager.name || "Branch Manager"} on WhatsApp`}
            >
              <WhatsappLogo size={15} weight="bold" /> WhatsApp Manager
            </button>
            <button
              onClick={() => handleShareWhatsApp("student")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-zinc-900 hover:bg-zinc-800 text-white text-xs font-bold uppercase tracking-wider transition-colors shadow-sm"
              title="Share receipt & schedule directly to student's WhatsApp"
            >
              <WhatsappLogo size={15} weight="bold" /> Student
            </button>
            {allotment?.assigned_trainer?.phone && (
              <button
                onClick={() => handleShareWhatsApp("trainer")}
                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold uppercase tracking-wider transition-colors shadow-sm"
                title="Send slot & student details to allotted instructor"
              >
                <WhatsappLogo size={14} weight="bold" /> Trainer
              </button>
            )}
            <button
              onClick={handleCopyText}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-zinc-100 hover:bg-zinc-200 text-zinc-800 border border-zinc-300 text-xs font-bold uppercase tracking-wider transition-colors"
              title="Copy formatted invoice & schedule text to clipboard"
            >
              <Copy size={14} weight="bold" /> Copy Text
            </button>
            <button
              onClick={handlePrint}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-zinc-300 hover:bg-zinc-100 text-zinc-900 text-xs font-bold uppercase tracking-wider transition-colors shadow-sm"
              title="Print official agreement slip or Save as PDF"
            >
              <Printer size={15} weight="bold" /> Print / PDF
            </button>
            <button
              onClick={onClose}
              className="p-1.5 hover:bg-zinc-200 text-zinc-600 transition-colors"
              title="Close modal"
            >
              <X size={18} weight="bold" />
            </button>
          </div>
        </div>

        {loading ? (
          <div className="p-16 text-center text-xs font-bold uppercase tracking-wider text-zinc-500 animate-pulse">
            Generating Official Admission Slip &amp; Invoice…
          </div>
        ) : (
          <div id="printable-invoice" className="p-8 font-sans text-zinc-900 print:p-0">
            {/* Header: School Info & Invoice Number */}
            <div className="border-b-2 border-zinc-900 pb-5 mb-5 flex items-start justify-between gap-4 flex-wrap">
              <div>
                <h1 className="font-heading text-2xl sm:text-3xl font-black tracking-tight leading-none text-zinc-950 uppercase">
                  {school.name}
                </h1>
                <p className="text-xs font-bold text-zinc-600 mt-1 uppercase tracking-wider">
                  {school.tagline}
                </p>
                <p className="text-xs text-zinc-700 mt-1 max-w-md">
                  📍 {school.address}
                </p>
                <div className="flex items-center gap-3 text-xs text-zinc-600 mt-1 font-mono-data">
                  <span>Tel: {school.phone}</span>
                  <span>·</span>
                  <span>RTO Reg: {school.rto_registration}</span>
                </div>
              </div>

              <div className="text-right">
                <div className="label-tag">Admission Invoice</div>
                <div className="font-mono-data text-base font-black tracking-tight text-zinc-950 mt-1">
                  {data.invoice_number}
                </div>
                <div className="text-xs text-zinc-500 font-mono-data mt-0.5">
                  Date: {data.date}
                </div>
                <div className="mt-2">
                  <span
                    className={`inline-block px-2.5 py-1 text-xs font-black uppercase tracking-wider border-2 ${
                      financials.is_fully_paid
                        ? "border-emerald-600 text-emerald-800 bg-emerald-50"
                        : "border-amber-600 text-amber-800 bg-amber-50"
                    }`}
                  >
                    {financials.status_label}
                  </span>
                </div>
              </div>
            </div>

            {/* Student & Allotment 2-Column Section */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              {/* Column 1: Student Information */}
              <div className="border border-zinc-200 p-4 bg-zinc-50/50">
                <div className="label-tag text-[10px] text-zinc-500 uppercase tracking-wider mb-2 font-black border-b border-zinc-200 pb-1">
                  Student Details
                </div>
                <div className="space-y-1.5 text-xs">
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Name:</span>
                    <span className="font-bold text-zinc-900">{student.name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Phone:</span>
                    <span className="font-mono-data font-bold text-zinc-800">{student.phone}</span>
                  </div>
                  {student.email && (
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Email:</span>
                      <span className="text-zinc-800">{student.email}</span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-zinc-500">License Category:</span>
                    <span className="font-bold uppercase text-zinc-900">{student.license_type}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Branch:</span>
                    <span className="font-bold text-zinc-900">{student.location} Branch</span>
                  </div>
                  {student.needs_pickup && student.pickup_address && (
                    <div className="pt-1.5 border-t border-zinc-200">
                      <span className="text-[10px] text-zinc-500 font-bold uppercase block">Pickup Location:</span>
                      <span className="text-zinc-700 italic">{student.pickup_address}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Column 2: Allotment & Timings */}
              <div className="border-2 border-zinc-900 p-4 bg-yellow-50/40">
                <div className="label-tag text-[10px] text-zinc-900 uppercase tracking-wider mb-2 font-black border-b border-zinc-300 pb-1">
                  Allotment &amp; Schedule Timings (Must &amp; Should)
                </div>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between items-center bg-white p-2 border border-zinc-300">
                    <span className="font-bold text-zinc-700 flex items-center gap-1">
                      <Clock size={14} weight="bold" /> Allotted Hour:
                    </span>
                    <span className="font-mono-data font-black text-sm text-zinc-950 bg-yellow-300 px-2 py-0.5">
                      {formatSlot12(allotment.slot_hour)}
                    </span>
                  </div>

                  <div className="flex justify-between">
                    <span className="text-zinc-600 flex items-center gap-1">
                      <User size={13} weight="bold" /> Assigned Instructor:
                    </span>
                    <span className="font-bold text-zinc-900">
                      {allotment.assigned_trainer?.name || "Assigned at Branch"}
                    </span>
                  </div>

                  {allotment.assigned_trainer?.phone && (
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Instructor Phone:</span>
                      <span className="font-mono-data font-bold text-zinc-800">
                        {allotment.assigned_trainer.phone}
                      </span>
                    </div>
                  )}

                  {student.needs_pickup && (
                    <>
                      <div className="flex justify-between">
                        <span className="text-zinc-500">Pickup Driver:</span>
                        <span className="font-bold text-zinc-800">
                          {allotment.pickup_trainer?.name || "Designated Pickup"}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-zinc-500">Drop Driver:</span>
                        <span className="font-bold text-zinc-800">
                          {allotment.drop_trainer?.name || "Designated Drop"}
                        </span>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* 12 Working Days Training Schedule Card */}
            <div className="mb-6">
              <div className="label-tag text-[11px] font-black uppercase tracking-wider mb-2 flex items-center justify-between">
                <span>12 Working Days Class Schedule (Sundays &amp; Declared Holidays Excluded)</span>
                <span className="text-zinc-500 font-mono-data font-normal">Course Duration: 12 Working Sessions</span>
              </div>
              <div className="border border-zinc-300 overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="bg-zinc-100 border-b border-zinc-300 font-bold text-zinc-700 uppercase tracking-wider text-[10px]">
                    <tr>
                      <th className="py-1.5 px-2.5">Session</th>
                      <th className="py-1.5 px-2.5">Scheduled Date</th>
                      <th className="py-1.5 px-2.5">Time Slot</th>
                      <th className="py-1.5 px-2.5">Status</th>
                      <th className="py-1.5 px-2.5 text-right">Student Sign</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-200">
                    {schedule.slice(0, 12).map((c) => (
                      <tr key={c.class_number} className="hover:bg-zinc-50/50">
                        <td className="py-1.5 px-2.5 font-bold font-mono-data">
                          Class {c.class_number}
                        </td>
                        <td className="py-1.5 px-2.5 font-mono-data font-semibold text-zinc-900">
                          {c.scheduled_date || "—"}
                        </td>
                        <td className="py-1.5 px-2.5 font-mono-data text-zinc-600">
                          {formatSlot12(allotment.slot_hour)}
                        </td>
                        <td className="py-1.5 px-2.5">
                          <span
                            className={`px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider ${
                              c.status === "completed"
                                ? "bg-emerald-100 text-emerald-800"
                                : c.status === "missed"
                                ? "bg-red-100 text-red-800"
                                : "bg-zinc-100 text-zinc-600"
                            }`}
                          >
                            {c.status}
                          </span>
                        </td>
                        <td className="py-1.5 px-2.5 text-right text-zinc-300 font-mono-data">
                          __________
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Fee & Payment Ledger */}
            <div className="mb-6">
              <div className="label-tag text-[11px] font-black uppercase tracking-wider mb-2">
                Fee Receipt &amp; Payment Statement
              </div>
              <div className="border border-zinc-300 overflow-x-auto mb-3">
                <table className="w-full text-xs text-left">
                  <thead className="bg-zinc-100 border-b border-zinc-300 font-bold text-zinc-700 uppercase tracking-wider text-[10px]">
                    <tr>
                      <th className="py-2 px-3">Description</th>
                      <th className="py-2 px-3 text-right">Agreed Total</th>
                      <th className="py-2 px-3 text-right">Amount Paid</th>
                      <th className="py-2 px-3 text-right">Balance Remaining</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b border-zinc-200">
                      <td className="py-2.5 px-3">
                        <div className="font-bold text-zinc-900">
                          Comprehensive 12 Working Days Driving Training Course
                        </div>
                        <div className="text-[10px] text-zinc-500">
                          Category: {student.license_type?.toUpperCase()} · Branch: {student.location}
                        </div>
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono-data font-bold">
                        ₹{financials.fees_total?.toLocaleString("en-IN")}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono-data font-bold text-emerald-700">
                        ₹{financials.fees_paid?.toLocaleString("en-IN")}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono-data font-black text-amber-800">
                        ₹{financials.fees_balance?.toLocaleString("en-IN")}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* Transactions Ledger (if any) */}
              {financials.payments_ledger && financials.payments_ledger.length > 0 && (
                <div className="bg-zinc-50 p-2.5 border border-zinc-200 text-xs">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-1.5">
                    Recorded Payment Receipts
                  </div>
                  <div className="space-y-1">
                    {financials.payments_ledger.map((p, idx) => (
                      <div key={p.id || idx} className="flex justify-between text-[11px] font-mono-data">
                        <span>
                          Receipt #{idx + 1} ({p.date}) — Mode: <span className="uppercase font-bold">{p.method}</span>
                        </span>
                        <span className="font-bold text-zinc-900">
                          ₹{Number(p.amount).toLocaleString("en-IN")}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Mandatory Instructions & Reporting Rules */}
            <div className="mb-6 border-2 border-zinc-900 p-4 bg-zinc-50">
              <div className="label-tag text-[11px] text-zinc-950 uppercase tracking-wider mb-2 font-black flex items-center gap-1.5">
                <ShieldCheck size={16} weight="bold" /> Mandatory Student Rules &amp; Reporting Guidelines
              </div>
              <ol className="list-decimal list-inside space-y-1.5 text-[11px] text-zinc-800 leading-relaxed">
                {instructions.map((inst, idx) => (
                  <li key={idx} className="font-medium">
                    {inst}
                  </li>
                ))}
              </ol>
            </div>

            {/* Signatures & Seal */}
            <div className="pt-8 border-t-2 border-zinc-900 grid grid-cols-2 gap-8 text-xs">
              <div>
                <div className="border-b border-zinc-400 pb-8 mb-1" />
                <div className="font-bold text-zinc-900">Student's Signature</div>
                <div className="text-[10px] text-zinc-500">
                  I accept the allotted timings, 12-day schedule, and driving school rules.
                </div>
              </div>
              <div className="text-right">
                <div className="border-b border-zinc-400 pb-8 mb-1" />
                <div className="font-bold text-zinc-900">For {school.name}</div>
                <div className="text-[10px] text-zinc-500">
                  Authorized Branch Officer &amp; Official Seal
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
