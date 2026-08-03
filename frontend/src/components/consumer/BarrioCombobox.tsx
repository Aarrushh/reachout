import { useMemo, useState } from "react";

import { matchBarrios } from "../../lib/matchBarrios";
import { t, type Lang } from "../../i18n/strings";

interface Props {
  selected: string | null;
  onSelect: (name: string | null) => void;
  lang: Lang;
}

export default function BarrioCombobox({ selected, onSelect, lang }: Props) {
  const [input, setInput] = useState(selected ?? "");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const options = useMemo(() => matchBarrios(input), [input]);

  function pick(name: string) {
    onSelect(name);
    setInput(name);
    setOpen(false);
  }

  return (
    <div className="barrio-combobox" role="combobox" aria-expanded={open} aria-haspopup="listbox">
      <input
        value={input}
        placeholder={t(lang, "entry.barrioPlaceholder")}
        onChange={(e) => { setInput(e.target.value); setOpen(true); setActive(0); onSelect(null); }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { setActive((a) => Math.min(a + 1, options.length - 1)); e.preventDefault(); }
          else if (e.key === "ArrowUp") { setActive((a) => Math.max(a - 1, 0)); e.preventDefault(); }
          else if (e.key === "Enter" && open && options[active]) { pick(options[active]); e.preventDefault(); }
          else if (e.key === "Escape") setOpen(false);
        }}
      />
      {open && options.length > 0 && (
        // preventDefault on mousedown keeps the input focused, so the click
        // lands before any blur — no close-timer race needed.
        <ul role="listbox" onMouseDown={(e) => e.preventDefault()}>
          {options.map((name, i) => (
            <li
              key={name}
              role="option"
              aria-selected={i === active}
              className={i === active ? "active" : ""}
              onClick={() => pick(name)}
              onMouseEnter={() => setActive(i)}
            >
              {name}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
