"use client";

import { useState } from "react";
import type { DebateHistory } from "@/lib/types";
import { deleteHistory, clearHistory } from "@/lib/history";
import { downloadMarkdown } from "@/lib/markdown";

interface Props {
  history: DebateHistory[];
  onSelect: (entry: DebateHistory) => void;
  onHistoryChange: (updated: DebateHistory[]) => void;
}

export function HistoryPanel({ history, onSelect, onHistoryChange }: Props) {
  const [open, setOpen] = useState(false);

  if (history.length === 0) return null;

  function handleDelete(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    onHistoryChange(deleteHistory(id));
  }

  function handleClear() {
    clearHistory();
    onHistoryChange([]);
  }

  function handleDownload(entry: DebateHistory, e: React.MouseEvent) {
    e.stopPropagation();
    downloadMarkdown(entry);
  }

  return (
    <div className="mb-6 rounded-xl border border-gray-200 bg-white shadow-sm">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-xl"
      >
        <span>📋 토론 히스토리 ({history.length}건)</span>
        <span className="text-gray-400">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="border-t border-gray-100">
          <div className="flex justify-end px-4 py-2">
            <button
              onClick={handleClear}
              className="text-xs text-red-400 hover:text-red-600"
            >
              전체 삭제
            </button>
          </div>

          <ul className="max-h-72 overflow-y-auto divide-y divide-gray-50">
            {history.map((entry) => {
              const date = new Date(entry.timestamp).toLocaleString("ko-KR", {
                month: "2-digit",
                day: "2-digit",
                hour: "2-digit",
                minute: "2-digit",
              });
              const consensus = entry.verdict?.consensus_level;
              const levelColor =
                consensus === undefined
                  ? "bg-gray-200 text-gray-500"
                  : consensus >= 70
                  ? "bg-green-100 text-green-700"
                  : consensus >= 40
                  ? "bg-yellow-100 text-yellow-700"
                  : "bg-red-100 text-red-700";

              return (
                <li
                  key={entry.id}
                  onClick={() => onSelect(entry)}
                  className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-gray-50 group"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-800 truncate">{entry.question}</p>
                    <p className="text-xs text-gray-400 mt-0.5">{date}</p>
                  </div>

                  {consensus !== undefined && (
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium shrink-0 ${levelColor}`}>
                      {consensus}%
                    </span>
                  )}

                  <button
                    onClick={(e) => handleDownload(entry, e)}
                    title="마크다운 저장"
                    className="text-gray-300 hover:text-blue-500 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    ⬇
                  </button>
                  <button
                    onClick={(e) => handleDelete(entry.id, e)}
                    title="삭제"
                    className="text-gray-300 hover:text-red-500 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    ✕
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
