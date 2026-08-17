import { type FormEvent } from "react";

import { t, type Lang } from "../../i18n/strings";
import ClickSpark from "./reactbits/ClickSpark";

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  lang: Lang;
  disabled?: boolean;
  autoFocus?: boolean;
}

export default function SearchInput({ value, onChange, onSubmit, lang, disabled, autoFocus }: Props) {
  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (value.trim()) onSubmit();
  }
  return (
    <form className="search-input" onSubmit={handleSubmit}>
      <input
        name="q"
        value={value}
        autoFocus={autoFocus}
        placeholder={t(lang, "search.placeholder")}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          // A disabled submit button suppresses implicit form submission, so
          // Enter would be silently swallowed; route it to onSubmit so the
          // caller can show why the search can't run yet.
          if (e.key === "Enter" && disabled) {
            e.preventDefault();
            if (value.trim()) onSubmit();
          }
        }}
        aria-label={t(lang, "search.submit")}
      />
      {/* Wraps only the submit control, per D12: the "broadcast" gesture
       * fires at the moment of broadcast, not on every keystroke in the
       * field beside it. */}
      <ClickSpark sparkColor="var(--terracotta)" sparkRadius={18} sparkCount={8}>
        <button type="submit" disabled={disabled || !value.trim()}>
          {t(lang, "search.submit")}
        </button>
      </ClickSpark>
    </form>
  );
}
