import { useState } from "react";
import type { CharacterListItem } from "../../lib/types";

type Props = {
  items: CharacterListItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
};

export default function CharacterList({ items, selectedId, onSelect }: Props) {
  const [search, setSearch] = useState("");
  const [faction, setFaction] = useState("");

  const factions = [...new Set(items.map((c) => c.faction).filter(Boolean))] as string[];

  const filtered = items.filter((c) => {
    if (search && !c.name.includes(search)) return false;
    if (faction && c.faction !== faction) return false;
    return true;
  });

  return (
    <div className="border-r border-border flex flex-col h-full">
      <div className="p-3 space-y-2 border-b border-border/50">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="搜索角色..."
          className="w-full h-8 px-3 rounded-sm border border-border bg-panel text-sm text-txt focus:outline-none focus:border-accent"
        />
        <select
          value={faction}
          onChange={(e) => setFaction(e.target.value)}
          className="w-full h-8 px-2 rounded-sm border border-border bg-panel text-sm text-txt-soft"
        >
          <option value="">全部阵营</option>
          {factions.map((f) => <option key={f} value={f}>{f}</option>)}
        </select>
      </div>
      <div className="overflow-y-auto flex-1">
        {filtered.map((c) => (
          <div
            key={c.id}
            onClick={() => onSelect(c.id)}
            className={`px-4 py-3 border-b border-border/50 cursor-pointer transition-colors ${
              c.id === selectedId ? "bg-accent-soft" : "hover:bg-panel-muted"
            }`}
          >
            <p className="text-md text-txt font-medium">{c.name}</p>
            <div className="flex gap-3 text-xs text-txt-faint mt-1">
              {c.faction && <span>{c.faction}</span>}
              <span>{c.eventCount} 事件</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
