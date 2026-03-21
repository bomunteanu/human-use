import { useEffect, useRef, useState } from "react";
import { ChevronDown, X } from "lucide-react";

interface Country {
  code: string;
  name: string;
}

const CONTINENTS: Record<string, Country[]> = {
  "North America": [
    { code: "US", name: "United States" },
    { code: "CA", name: "Canada" },
    { code: "MX", name: "Mexico" },
  ],
  "Latin America": [
    { code: "BR", name: "Brazil" },
    { code: "AR", name: "Argentina" },
    { code: "CO", name: "Colombia" },
    { code: "CL", name: "Chile" },
    { code: "PE", name: "Peru" },
  ],
  Europe: [
    { code: "GB", name: "United Kingdom" },
    { code: "DE", name: "Germany" },
    { code: "FR", name: "France" },
    { code: "IT", name: "Italy" },
    { code: "ES", name: "Spain" },
    { code: "NL", name: "Netherlands" },
    { code: "PL", name: "Poland" },
    { code: "SE", name: "Sweden" },
    { code: "PT", name: "Portugal" },
    { code: "AT", name: "Austria" },
    { code: "CH", name: "Switzerland" },
    { code: "BE", name: "Belgium" },
  ],
  Asia: [
    { code: "JP", name: "Japan" },
    { code: "CN", name: "China" },
    { code: "IN", name: "India" },
    { code: "KR", name: "South Korea" },
    { code: "ID", name: "Indonesia" },
    { code: "TH", name: "Thailand" },
    { code: "VN", name: "Vietnam" },
    { code: "PH", name: "Philippines" },
    { code: "MY", name: "Malaysia" },
    { code: "SG", name: "Singapore" },
  ],
  "Middle East": [
    { code: "AE", name: "UAE" },
    { code: "SA", name: "Saudi Arabia" },
    { code: "TR", name: "Turkey" },
    { code: "IL", name: "Israel" },
    { code: "EG", name: "Egypt" },
  ],
  Africa: [
    { code: "NG", name: "Nigeria" },
    { code: "ZA", name: "South Africa" },
    { code: "KE", name: "Kenya" },
    { code: "GH", name: "Ghana" },
    { code: "MA", name: "Morocco" },
  ],
  Oceania: [
    { code: "AU", name: "Australia" },
    { code: "NZ", name: "New Zealand" },
  ],
};

const ALL_COUNTRIES = Object.values(CONTINENTS).flat();
const CODE_TO_NAME = Object.fromEntries(ALL_COUNTRIES.map((c) => [c.code, c.name]));

interface TargetingSelectorProps {
  value: string[];
  onChange: (codes: string[]) => void;
  disabled?: boolean;
}

export function TargetingSelector({ value, onChange, disabled }: TargetingSelectorProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const toggle = (code: string) => {
    onChange(value.includes(code) ? value.filter((c) => c !== code) : [...value, code]);
  };

  const toggleContinent = (continent: string) => {
    const codes = CONTINENTS[continent].map((c) => c.code);
    const allSelected = codes.every((c) => value.includes(c));
    if (allSelected) {
      onChange(value.filter((c) => !codes.includes(c)));
    } else {
      const next = new Set(value);
      codes.forEach((c) => next.add(c));
      onChange([...next]);
    }
  };

  const isContinentSelected = (continent: string) =>
    CONTINENTS[continent].every((c) => value.includes(c.code));

  const isContinentPartial = (continent: string) =>
    !isContinentSelected(continent) && CONTINENTS[continent].some((c) => value.includes(c.code));

  const label =
    value.length === 0
      ? "Worldwide"
      : value.length <= 3
        ? value.map((c) => CODE_TO_NAME[c] ?? c).join(", ")
        : `${value.length} countries`;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 h-8 px-3 text-[13px] bg-[#0d1117] border border-[#21262d] text-[#7d8590] hover:text-[#e6edf3] hover:border-[#30363d] rounded-[6px] disabled:opacity-40 transition-colors whitespace-nowrap"
      >
        <span className={value.length > 0 ? "text-[#e6edf3]" : ""}>{label}</span>
        {value.length > 0 && (
          <span
            role="button"
            tabIndex={0}
            onClick={(e) => {
              e.stopPropagation();
              onChange([]);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.stopPropagation();
                onChange([]);
              }
            }}
            className="text-[#7d8590] hover:text-[#e6edf3] cursor-pointer"
          >
            <X size={12} />
          </span>
        )}
        <ChevronDown size={12} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute bottom-full left-0 mb-1 z-50 w-56 max-h-80 overflow-y-auto bg-[#161b22] border border-[#30363d] rounded-[6px] shadow-lg py-1">
          {/* Worldwide */}
          <button
            type="button"
            onClick={() => {
              onChange([]);
              setOpen(false);
            }}
            className={`w-full text-left px-3 py-1.5 text-[13px] hover:bg-[#21262d] transition-colors ${
              value.length === 0 ? "text-[#2f81f7]" : "text-[#e6edf3]"
            }`}
          >
            Worldwide
          </button>

          <div className="border-t border-[#21262d] my-1" />

          {Object.entries(CONTINENTS).map(([continent, countries]) => (
            <div key={continent}>
              {/* Continent row */}
              <div className="flex items-center gap-2 px-3 py-1.5 hover:bg-[#21262d] cursor-pointer" onClick={() => toggleContinent(continent)}>
                <span
                  className={`w-3.5 h-3.5 flex items-center justify-center rounded-[3px] border text-[10px] flex-shrink-0 ${
                    isContinentSelected(continent)
                      ? "bg-[#2f81f7] border-[#2f81f7] text-white"
                      : isContinentPartial(continent)
                        ? "bg-[#2f81f7]/30 border-[#2f81f7] text-[#2f81f7]"
                        : "border-[#30363d]"
                  }`}
                >
                  {isContinentSelected(continent) ? "✓" : isContinentPartial(continent) ? "−" : ""}
                </span>
                <span className="text-[12px] font-semibold text-[#7d8590] uppercase tracking-wide">
                  {continent}
                </span>
              </div>

              {/* Countries */}
              {countries.map((country) => (
                <div
                  key={country.code}
                  className="flex items-center gap-2 pl-6 pr-3 py-1 hover:bg-[#21262d] cursor-pointer"
                  onClick={() => toggle(country.code)}
                >
                  <span
                    className={`w-3.5 h-3.5 flex items-center justify-center rounded-[3px] border text-[10px] flex-shrink-0 ${
                      value.includes(country.code)
                        ? "bg-[#2f81f7] border-[#2f81f7] text-white"
                        : "border-[#30363d]"
                    }`}
                  >
                    {value.includes(country.code) ? "✓" : ""}
                  </span>
                  <span className="text-[13px] text-[#e6edf3]">{country.name}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
