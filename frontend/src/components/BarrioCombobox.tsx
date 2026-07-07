import { useMemo, useRef, useState } from "react";

import { matchBarrios, type Barrio } from "../data/barrios";
import { t, type Lang } from "../i18n/strings";

interface Props {
  selected: Barrio | null;
  onSelect: (b: Barrio | null) => void;
  lang: Lang;
}

export default function BarrioCombobox({ selected, onSelect, lang }: Props) {
  const [input, setInput] = useState(selected?.name ?? "");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const blurTimer = useRef<number>(undefined);
  const options = useMemo(() => matchBarrios(input), [input]);

  function pick(b: Barrio) {
    onSelect(b);
    setInput(b.name);
    setOpen(false);
  }

  return (
    <div className="barrio-combobox" role="combobox" aria-expanded={open} aria-haspopup="listbox">
      <input
        value={input}
        placeholder={t(lang, "entry.barrioPlaceholder")}
        onChange={(e) => { setInput(e.target.value); setOpen(true); setActive(0); onSelect(null); }}
        onFocus={() => setOpen(true)}
        onBlur={() => { blurTimer.current = window.setTimeout(() => setOpen(false), 120); }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { setActive((a) => Math.min(a + 1, options.length - 1)); e.preventDefault(); }
          else if (e.key === "ArrowUp") { setActive((a) => Math.max(a - 1, 0)); e.preventDefault(); }
          else if (e.key === "Enter" && open && options[active]) { pick(options[active]); e.preventDefault(); }
          else if (e.key === "Escape") setOpen(false);
        }}
      />
      {open && options.length > 0 && (
        <ul role="listbox">
          {options.map((b, i) => (
            <li
              key={b.name}
              role="option"
              aria-selected={i === active}
              className={i === active ? "active" : ""}
              onMouseDown={() => { window.clearTimeout(blurTimer.current); pick(b); }}
              onMouseEnter={() => setActive(i)}
            >
              {b.name}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
