import { api } from "./api";
import { toast } from "sonner";

/**
 * Escapes a cell value for standard CSV compatibility with Microsoft Excel & Google Sheets.
 */
function escapeCsvValue(val) {
  if (val === null || val === undefined) return '""';
  const str = String(val).replace(/"/g, '""');
  return `"${str}"`;
}

/**
 * Exports any list of students to a clean, Excel-ready CSV file.
 * Automatically adds UTF-8 BOM (\uFEFF) so Microsoft Excel opens it perfectly.
 */
export function exportStudentsToCsv(students, filenamePrefix = "LearnAndDrive_Students") {
  if (!students || students.length === 0) {
    toast.error("No students to export");
    return;
  }

  const headers = [
    "Student Name",
    "Phone Number",
    "Branch Location",
    "Slot Time",
    "Status",
    "Joined Date",
    "Total Classes",
    "Completed Classes",
    "Remaining Classes",
    "Total Fees (₹)",
    "Fees Paid (₹)",
    "Balance Due (₹)",
    "Assigned Trainer",
    "Needs Pickup",
    "Pickup Address",
    "Drop Address",
    "Notes",
  ];

  const rows = students.map((s) => {
    const totalC = s.total_classes || 12;
    const completedC = s.classes_completed || 0;
    const remC = s.classes_remaining != null ? s.classes_remaining : Math.max(0, totalC - completedC);
    const feesTotal = s.fees_total || 0;
    const feesPaid = s.fees_paid || 0;
    const feesDue = Math.max(0, feesTotal - feesPaid);

    return [
      escapeCsvValue(s.name || ""),
      escapeCsvValue(s.phone ? `'${s.phone}` : ""), // Prepend apostrophe so Excel keeps leading 0 / doesn't truncate phone
      escapeCsvValue(s.location || ""),
      escapeCsvValue(s.slot_time || ""),
      escapeCsvValue(s.status || "active"),
      escapeCsvValue(s.joined_date || s.created_at?.slice(0, 10) || ""),
      escapeCsvValue(totalC),
      escapeCsvValue(completedC),
      escapeCsvValue(remC),
      escapeCsvValue(feesTotal),
      escapeCsvValue(feesPaid),
      escapeCsvValue(feesDue),
      escapeCsvValue(s.trainer_name || s.assigned_trainer_id || ""),
      escapeCsvValue(s.needs_pickup ? "Yes" : "No"),
      escapeCsvValue(s.pickup_address || ""),
      escapeCsvValue(s.drop_address || ""),
      escapeCsvValue(s.notes || ""),
    ].join(",");
  });

  const csvContent = "\uFEFF" + [headers.join(","), ...rows].join("\r\n");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const dateStr = new Date().toISOString().slice(0, 10);
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", `${filenamePrefix}_${dateStr}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
  toast.success(`Exported ${students.length} students to Excel CSV file!`);
}

/**
 * Downloads the master multi-sheet Historical Archive Excel (.xlsx) file.
 */
export async function downloadMasterArchiveExcel() {
  const toastId = toast.loading("Preparing Master Historical Archive Excel (.xlsx)…");
  try {
    const response = await api.get("/reports/export-archive-excel", {
      responseType: "blob",
    });
    const blob = new Blob([response.data], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `LearnAndDrive_Historical_Archive_${new Date().toISOString().slice(0, 10)}.xlsx`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    toast.success("Master Archive Excel downloaded successfully!", { id: toastId });
  } catch (err) {
    toast.error("Failed to download Master Excel file. Please try again.", { id: toastId });
  }
}
