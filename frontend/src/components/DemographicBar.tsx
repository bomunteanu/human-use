import { useEffect, useRef, useState } from "react";
import { ChevronDown, X } from "lucide-react";
import type { AgeGroup, Gender, TargetingConfig } from "../types";
import { emptyTargeting } from "../types";

// ─── Country data (same as TargetingSelector) ────────────────────────────────

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

// ─── Age group & gender options ───────────────────────────────────────────────

const AGE_GROUPS: { value: AgeGroup; label: string }[] = [
  { value: "under_18", label: "Under 18" },
  { value: "18-24", label: "18–24" },
  { value: "25-34", label: "25–34" },
  { value: "35-44", label: "35–44" },
  { value: "45-54", label: "45–54" },
  { value: "55+", label: "55+" },
];

const GENDERS: { value: Gender; label: string }[] = [
  { value: "male", label: "Male" },
  { value: "female", label: "Female" },
  { value: "other", label: "Other" },
];

const COMMON_LANGUAGES = [
  { code: "en", name: "English" },
  { code: "es", name: "Spanish" },
  { code: "fr", name: "French" },
  { code: "de", name: "German" },
  { code: "pt", name: "Portuguese" },
  { code: "zh", name: "Chinese" },
  { code: "ja", name: "Japanese" },
  { code: "ko", name: "Korean" },
  { code: "ar", name: "Arabic" },
  { code: "hi", name: "Hindi" },
  { code: "it", name: "Italian" },
  { code: "ru", name: "Russian" },
  { code: "tr", name: "Turkish" },
  { code: "nl", name: "Dutch" },
  { code: "pl", name: "Polish" },
  { code: "sv", name: "Swedish" },
];

const LANG_CODE_TO_NAME = Object.fromEntries(COMMON_LANGUAGES.map((l) => [l.code, l.name]));

// ─── Shared dropdown helpers ──────────────────────────────────────────────────

function CheckboxItem({
  checked,
  partial,
  label,
  onClick,
  indent,
}: {
  checked: boolean;
  partial?: boolean;
  label: string;
  onClick: () => void;
  indent?: boolean;
}) {
  return (
    <div
      className={`flex items-center gap-2 ${indent ? "pl-6" : "px-3"} pr-3 py-1 hover:bg-[#21262d] cursor-pointer`}
      onClick={onClick}
    >
      <span
        className={`w-3.5 h-3.5 flex items-center justify-center rounded-[3px] border text-[10px] flex-shrink-0 ${
          checked
            ? "bg-[#2f81f7] border-[#2f81f7] text-white"
            : partial
              ? "bg-[#2f81f7]/30 border-[#2f81f7] text-[#2f81f7]"
              : "border-[#30363d]"
        }`}
      >
        {checked ? "✓" : partial ? "−" : ""}
      </span>
      <span className="text-[13px] text-[#e6edf3]">{label}</span>
    </div>
  );
}

// ─── Individual pill dropdowns ────────────────────────────────────────────────

function PillDropdown({
  label,
  active,
  disabled,
  onClear,
  children,
}: {
  label: string;
  active: boolean;
  disabled?: boolean;
  onClear?: () => void;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        className={`flex items-center gap-1 h-7 px-2.5 text-[12px] rounded-[5px] border transition-colors disabled:opacity-40 whitespace-nowrap ${
          active
            ? "bg-[#2f81f7]/10 border-[#2f81f7]/40 text-[#e6edf3] hover:border-[#2f81f7]/70"
            : "bg-transparent border-[#21262d] text-[#7d8590] hover:text-[#e6edf3] hover:border-[#30363d]"
        }`}
      >
        <span>{label}</span>
        {active && onClear && (
          <span
            role="button"
            tabIndex={0}
            onClick={(e) => {
              e.stopPropagation();
              onClear();
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.stopPropagation();
                onClear();
              }
            }}
            className="text-[#7d8590] hover:text-[#e6edf3] ml-0.5"
          >
            <X size={10} />
          </span>
        )}
        <ChevronDown size={10} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute bottom-full left-0 mb-1 z-50 w-52 max-h-72 overflow-y-auto bg-[#161b22] border border-[#30363d] rounded-[6px] shadow-lg py-1">
          {children}
        </div>
      )}
    </div>
  );
}

// ─── Country sub-dropdown (same continent logic as TargetingSelector) ─────────

function CountryDropdown({
  value,
  onChange,
  disabled,
}: {
  value: string[];
  onChange: (codes: string[]) => void;
  disabled?: boolean;
}) {
  const toggle = (code: string) =>
    onChange(value.includes(code) ? value.filter((c) => c !== code) : [...value, code]);

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

  const isContinentSelected = (c: string) => CONTINENTS[c].every((x) => value.includes(x.code));
  const isContinentPartial = (c: string) =>
    !isContinentSelected(c) && CONTINENTS[c].some((x) => value.includes(x.code));

  const label =
    value.length === 0
      ? "🌍 Worldwide"
      : value.length <= 3
        ? value.map((c) => CODE_TO_NAME[c] ?? c).join(", ")
        : `🌍 ${value.length} countries`;

  return (
    <PillDropdown
      label={label}
      active={value.length > 0}
      disabled={disabled}
      onClear={() => onChange([])}
    >
      <button
        type="button"
        onClick={() => onChange([])}
        className={`w-full text-left px-3 py-1.5 text-[13px] hover:bg-[#21262d] transition-colors ${
          value.length === 0 ? "text-[#2f81f7]" : "text-[#e6edf3]"
        }`}
      >
        Worldwide (all)
      </button>
      <div className="border-t border-[#21262d] my-1" />
      {Object.entries(CONTINENTS).map(([continent, countries]) => (
        <div key={continent}>
          <div
            className="flex items-center gap-2 px-3 py-1.5 hover:bg-[#21262d] cursor-pointer"
            onClick={() => toggleContinent(continent)}
          >
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
          {countries.map((country) => (
            <CheckboxItem
              key={country.code}
              checked={value.includes(country.code)}
              label={country.name}
              onClick={() => toggle(country.code)}
              indent
            />
          ))}
        </div>
      ))}
    </PillDropdown>
  );
}

// ─── Language sub-dropdown ────────────────────────────────────────────────────

function LanguageDropdown({
  value,
  onChange,
  disabled,
}: {
  value: string[];
  onChange: (codes: string[]) => void;
  disabled?: boolean;
}) {
  const toggle = (code: string) =>
    onChange(value.includes(code) ? value.filter((c) => c !== code) : [...value, code]);

  const label =
    value.length === 0
      ? "🗣 All languages"
      : value.length <= 2
        ? value.map((c) => LANG_CODE_TO_NAME[c] ?? c).join(", ")
        : `🗣 ${value.length} languages`;

  return (
    <PillDropdown
      label={label}
      active={value.length > 0}
      disabled={disabled}
      onClear={() => onChange([])}
    >
      <button
        type="button"
        onClick={() => onChange([])}
        className={`w-full text-left px-3 py-1.5 text-[13px] hover:bg-[#21262d] transition-colors ${
          value.length === 0 ? "text-[#2f81f7]" : "text-[#e6edf3]"
        }`}
      >
        All languages
      </button>
      <div className="border-t border-[#21262d] my-1" />
      {COMMON_LANGUAGES.map((lang) => (
        <CheckboxItem
          key={lang.code}
          checked={value.includes(lang.code)}
          label={lang.name}
          onClick={() => toggle(lang.code)}
        />
      ))}
    </PillDropdown>
  );
}

// ─── Age group sub-dropdown ───────────────────────────────────────────────────

function AgeGroupDropdown({
  value,
  onChange,
  disabled,
}: {
  value: AgeGroup[];
  onChange: (ages: AgeGroup[]) => void;
  disabled?: boolean;
}) {
  const toggle = (age: AgeGroup) =>
    onChange(value.includes(age) ? value.filter((a) => a !== age) : [...value, age]);

  const label =
    value.length === 0
      ? "👤 All ages"
      : value.length <= 2
        ? value.map((a) => AGE_GROUPS.find((g) => g.value === a)?.label ?? a).join(", ")
        : `👤 ${value.length} age groups`;

  return (
    <PillDropdown
      label={label}
      active={value.length > 0}
      disabled={disabled}
      onClear={() => onChange([])}
    >
      <button
        type="button"
        onClick={() => onChange([])}
        className={`w-full text-left px-3 py-1.5 text-[13px] hover:bg-[#21262d] transition-colors ${
          value.length === 0 ? "text-[#2f81f7]" : "text-[#e6edf3]"
        }`}
      >
        All ages
      </button>
      <div className="border-t border-[#21262d] my-1" />
      {AGE_GROUPS.map((ag) => (
        <CheckboxItem
          key={ag.value}
          checked={value.includes(ag.value)}
          label={ag.label}
          onClick={() => toggle(ag.value)}
        />
      ))}
    </PillDropdown>
  );
}

// ─── Gender sub-dropdown ──────────────────────────────────────────────────────

function GenderDropdown({
  value,
  onChange,
  disabled,
}: {
  value: Gender[];
  onChange: (genders: Gender[]) => void;
  disabled?: boolean;
}) {
  const toggle = (gender: Gender) =>
    onChange(value.includes(gender) ? value.filter((g) => g !== gender) : [...value, gender]);

  const label =
    value.length === 0
      ? "⚥ All genders"
      : value.map((g) => GENDERS.find((x) => x.value === g)?.label ?? g).join(", ");

  return (
    <PillDropdown
      label={label}
      active={value.length > 0}
      disabled={disabled}
      onClear={() => onChange([])}
    >
      <button
        type="button"
        onClick={() => onChange([])}
        className={`w-full text-left px-3 py-1.5 text-[13px] hover:bg-[#21262d] transition-colors ${
          value.length === 0 ? "text-[#2f81f7]" : "text-[#e6edf3]"
        }`}
      >
        All genders
      </button>
      <div className="border-t border-[#21262d] my-1" />
      {GENDERS.map((g) => (
        <CheckboxItem
          key={g.value}
          checked={value.includes(g.value)}
          label={g.label}
          onClick={() => toggle(g.value)}
        />
      ))}
    </PillDropdown>
  );
}

// ─── DemographicBar ───────────────────────────────────────────────────────────

interface DemographicBarProps {
  targeting: TargetingConfig;
  onChange: (targeting: TargetingConfig) => void;
  disabled?: boolean;
}

export function DemographicBar({ targeting, onChange, disabled }: DemographicBarProps) {
  const isDefault =
    targeting.country_codes.length === 0 &&
    targeting.languages.length === 0 &&
    targeting.age_groups.length === 0 &&
    targeting.genders.length === 0;

  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {isDefault ? (
        // Default state: single merged pill showing worldwide + all demographics
        <div className="flex items-center gap-1.5">
          <CountryDropdown
            value={targeting.country_codes}
            onChange={(codes) => onChange({ ...targeting, country_codes: codes })}
            disabled={disabled}
          />
          <span className="text-[11px] text-[#3d444d]">·</span>
          <LanguageDropdown
            value={targeting.languages}
            onChange={(langs) => onChange({ ...targeting, languages: langs })}
            disabled={disabled}
          />
          <span className="text-[11px] text-[#3d444d]">·</span>
          <AgeGroupDropdown
            value={targeting.age_groups}
            onChange={(ages) => onChange({ ...targeting, age_groups: ages })}
            disabled={disabled}
          />
          <span className="text-[11px] text-[#3d444d]">·</span>
          <GenderDropdown
            value={targeting.genders}
            onChange={(genders) => onChange({ ...targeting, genders: genders })}
            disabled={disabled}
          />
        </div>
      ) : (
        // Active state: individual pills + a clear-all
        <div className="flex items-center gap-1.5 flex-wrap">
          <CountryDropdown
            value={targeting.country_codes}
            onChange={(codes) => onChange({ ...targeting, country_codes: codes })}
            disabled={disabled}
          />
          <LanguageDropdown
            value={targeting.languages}
            onChange={(langs) => onChange({ ...targeting, languages: langs })}
            disabled={disabled}
          />
          <AgeGroupDropdown
            value={targeting.age_groups}
            onChange={(ages) => onChange({ ...targeting, age_groups: ages })}
            disabled={disabled}
          />
          <GenderDropdown
            value={targeting.genders}
            onChange={(genders) => onChange({ ...targeting, genders: genders })}
            disabled={disabled}
          />
          <button
            type="button"
            onClick={() => onChange(emptyTargeting())}
            disabled={disabled}
            className="h-7 px-2 text-[11px] text-[#7d8590] hover:text-[#e6edf3] transition-colors disabled:opacity-40"
            title="Reset to Worldwide / all demographics"
          >
            Reset
          </button>
        </div>
      )}
    </div>
  );
}
