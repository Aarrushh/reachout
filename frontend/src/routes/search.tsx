/**
 * Route module: search entry. Reads/writes URL query params only — no
 * visuals, no layout. Visual design is a separate future phase.
 */
import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

export default function SearchRoute() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [near, setNear] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const params = new URLSearchParams({ q });
    if (near) params.set("near", near);
    navigate(`/results?${params.toString()}`);
  }

  return (
    <form onSubmit={handleSubmit}>
      <input name="q" value={q} onChange={(e) => setQ(e.target.value)} />
      <input name="near" value={near} onChange={(e) => setNear(e.target.value)} />
      <button type="submit">Search</button>
    </form>
  );
}
