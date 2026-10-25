import React, { useState } from "react";
import { Copy, Check } from "@phosphor-icons/react";
import { toast } from "sonner";

export default function CopyButton({
  text,
  label = "Copy",
  successMessage,
  size = 13,
  className = "",
  showText = false,
  title,
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e) => {
    e.stopPropagation();
    e.preventDefault();
    if (!text) {
      toast.error("No phone number to copy");
      return;
    }
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(String(text).trim());
      } else {
        const ta = document.createElement("textarea");
        ta.value = String(text).trim();
        ta.style.position = "fixed";
        ta.style.left = "-999999px";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      setCopied(true);
      toast.success(successMessage || `Copied: ${text}`);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Failed to copy");
    }
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      title={title || label || `Copy ${text}`}
      aria-label={title || label || `Copy ${text}`}
      className={`inline-flex items-center gap-1 p-1 rounded transition-colors text-zinc-500 hover:text-zinc-900 hover:bg-zinc-200/70 active:scale-95 ${className}`}
    >
      {copied ? (
        <Check size={size} weight="bold" className="text-emerald-600 animate-in fade-in" />
      ) : (
        <Copy size={size} weight="bold" />
      )}
      {showText && (
        <span className="text-xs font-semibold">
          {copied ? "Copied" : label}
        </span>
      )}
    </button>
  );
}
