// =====================================================================
// LEARN & DRIVE - GOOGLE SHEETS REAL-TIME ENROLLMENT SYNC
// =====================================================================
// How to set up in 60 seconds with learnanddrive2@gmail.com:
// 1. Open Google Sheets (https://sheets.new) in your browser.
// 2. Name your sheet e.g. "Learn & Drive - Student Admissions"
// 3. Click Extensions > Apps Script in the menu bar.
// 4. Delete any code there, paste THIS ENTIRE SCRIPT, and click Save.
// 5. Click "Deploy" (top right button) > "New deployment"
//    - Select type: "Web app" (click gear icon next to Select type)
//    - Description: "Learn & Drive Student Webhook"
//    - Execute as: "Me (learnanddrive2@gmail.com)"
//    - Who has access: "Anyone" (allows the website to send records)
// 6. Click "Deploy", click "Authorize access" (choose your Gmail), and COPY the Web App URL:
//    (It looks like: https://script.google.com/macros/s/AKfycb.../exec)
// 7. Share that URL with me, and your website will automatically append
//    every student upload directly into this Google Sheet in real-time!
// =====================================================================

function doPost(e) {
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    var data = JSON.parse(e.postData.contents);
    
    // Auto-create headers if sheet is empty
    if (sheet.getLastRow() === 0) {
      sheet.appendRow([
        "Timestamp",
        "Student ID",
        "Student Name",
        "Phone Number",
        "Branch / Location",
        "Time Slot (12h)",
        "Joining Date",
        "Assigned Trainer",
        "Course Days",
        "Total Fees (₹)",
        "Fees Paid (₹)",
        "Balance Due (₹)",
        "License Type",
        "Pickup Needed",
        "Pickup Address",
        "Status",
        "Notes"
      ]);
      // Format header row (Dark Navy + Bold White)
      var headerRange = sheet.getRange(1, 1, 1, 17);
      headerRange.setBackground("#1E3A8A");
      headerRange.setFontColor("#FFFFFF");
      headerRange.setFontWeight("bold");
      sheet.setFrozenRows(1);
    }
    
    // Append the student record
    sheet.appendRow([
      new Date().toLocaleString("en-IN", { timeZone: "Asia/Kolkata" }),
      data.student_id || "",
      data.name || "",
      data.phone || "",
      data.branch || "Khajaguda",
      data.slot_time || "",
      data.joining_date || "",
      data.trainer || "Unassigned",
      data.total_classes || 12,
      data.fees_total || 0,
      data.fees_paid || 0,
      data.balance_due || 0,
      data.license_type || "4W",
      data.needs_pickup || "No",
      data.pickup_address || "",
      data.status || "active",
      data.notes || ""
    ]);
    
    return ContentService.createTextOutput(JSON.stringify({ "status": "success", "row": sheet.getLastRow() }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ "status": "error", "message": err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}
