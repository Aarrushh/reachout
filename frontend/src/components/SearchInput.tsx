import { type FormEvent } from "react";

import { t, type Lang } from "../i18n/strings";

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
        aria-label={t(lang, "search.submit")}
      />
      <button type="submit" disabled={disabled || !value.trim()}>
        {t(lang, "search.submit")}
      </button>
    </form>
  );
}
