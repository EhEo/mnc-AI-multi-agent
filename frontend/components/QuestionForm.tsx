"use client";

interface Props {
  onSubmit: (question: string) => void;
  disabled: boolean;
}

export function QuestionForm({ onSubmit, disabled }: Props) {
  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const question = (data.get("question") as string).trim();
    if (question) {
      onSubmit(question);
      e.currentTarget.reset();
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        name="question"
        type="text"
        placeholder="전문가들에게 질문하세요..."
        disabled={disabled}
        className="flex-1 rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-900
                   placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-400
                   disabled:opacity-50"
      />
      <button
        type="submit"
        disabled={disabled}
        className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white
                   hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {disabled ? "토론 중..." : "토론 시작"}
      </button>
    </form>
  );
}
