/*
 * ResearchPdfDocument
 *
 * Pure @react-pdf/renderer document. Charts arrive as PNG data URLs (rasterized
 * from recharts SVG via canvas in OrdersPanel — SVG data URLs are unreliable in
 * react-pdf for complex SVGs with <clipPath>/<defs>).
 *
 * Markdown rendering: section.content is Claude markdown. We parse two levels:
 *   Block  — "- " bullets, "## " subheadings, bare lines as paragraphs
 *   Inline — **bold** and *italic* as nested <Text> spans with different fontFamily
 */
import { Document, Image, Page, StyleSheet, Text, View } from "@react-pdf/renderer";
import type { BriefSection, OrderState } from "../types";

interface Props {
  title: string;
  sections: BriefSection[];
  completedOrders: OrderState[];
  svgCaptures: Map<string, string>;
}

const S = StyleSheet.create({
  page: {
    paddingTop: 48,
    paddingBottom: 56,
    paddingHorizontal: 48,
    fontFamily: "Helvetica",
    backgroundColor: "#ffffff",
    fontSize: 11,
    color: "#24292f",
    lineHeight: 1.6,
  },
  question: {
    fontSize: 18,
    fontFamily: "Helvetica-Bold",
    marginBottom: 24,
    color: "#0d1117",
    lineHeight: 1.3,
  },
  sectionTitle: {
    fontSize: 13,
    fontFamily: "Helvetica-Bold",
    marginBottom: 8,
    color: "#0d1117",
  },
  subheading: {
    fontSize: 12,
    fontFamily: "Helvetica-Bold",
    color: "#0d1117",
    marginTop: 8,
    marginBottom: 4,
  },
  paragraph: {
    fontSize: 11,
    color: "#57606a",
    lineHeight: 1.7,
    marginBottom: 4,
  },
  // Inline style overrides (fontFamily only — nested inside paragraph)
  bold: { fontFamily: "Helvetica-Bold" },
  italic: { fontFamily: "Helvetica-Oblique" },
  bulletRow: {
    flexDirection: "row",
    marginBottom: 3,
    paddingLeft: 8,
  },
  // Wrap the dot in a View with a fixed width so react-pdf's flex engine
  // actually reserves the space — a bare <Text width={14}> is ignored.
  bulletDotWrapper: {
    width: 14,
    flexShrink: 0,
  },
  bulletDot: {
    fontSize: 11,
    color: "#57606a",
    lineHeight: 1.7,
  },
  bulletText: {
    fontSize: 11,
    color: "#57606a",
    lineHeight: 1.7,
    flex: 1,
  },
  divider: {
    borderBottomWidth: 0.5,
    borderBottomColor: "#d0d7de",
    marginVertical: 16,
  },
  tableWrapper: { marginBottom: 8 },
  tableHeaderRow: {
    flexDirection: "row",
    borderBottomWidth: 1,
    borderBottomColor: "#24292f",
    backgroundColor: "#f6f8fa",
  },
  tableRow: {
    flexDirection: "row",
    borderBottomWidth: 0.5,
    borderBottomColor: "#d0d7de",
  },
  tableCellHeader: {
    flex: 1,
    padding: 4,
    fontSize: 10,
    fontFamily: "Helvetica-Bold",
    color: "#24292f",
  },
  tableCell: {
    flex: 1,
    padding: 4,
    fontSize: 10,
    color: "#57606a",
  },
  chartsHeading: {
    fontSize: 13,
    fontFamily: "Helvetica-Bold",
    marginBottom: 12,
    color: "#0d1117",
  },
  chartBlock: { marginBottom: 20 },
  chartQuestion: {
    fontSize: 10,
    color: "#57606a",
    marginBottom: 6,
    fontFamily: "Helvetica-Oblique",
  },
  chartImage: { width: "100%", height: 110 },
  footer: {
    position: "absolute",
    bottom: 28,
    left: 48,
    right: 48,
    fontSize: 9,
    color: "#8c959f",
    textAlign: "center",
  },
});

// ---------------------------------------------------------------------------
// Inline markdown parser
// ---------------------------------------------------------------------------

interface Segment {
  text: string;
  bold: boolean;
  italic: boolean;
}

function parseInline(text: string): Segment[] {
  const out: Segment[] = [];
  const re = /\*\*([^*]+)\*\*|\*([^*]+)\*/g;
  let last = 0;
  let m: RegExpExecArray | null;

  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push({ text: text.slice(last, m.index), bold: false, italic: false });
    if (m[1] !== undefined) out.push({ text: m[1], bold: true, italic: false });
    else out.push({ text: m[2], bold: false, italic: true });
    last = m.index + m[0].length;
  }

  if (last < text.length) out.push({ text: text.slice(last), bold: false, italic: false });
  return out.length > 0 ? out : [{ text, bold: false, italic: false }];
}

// Renders a text line with inline bold/italic using the paragraph style.
function ParagraphLine({ text }: { text: string }) {
  const segs = parseInline(text);

  if (segs.length === 1 && !segs[0].bold && !segs[0].italic) {
    return <Text style={S.paragraph}>{text}</Text>;
  }

  return (
    <Text style={S.paragraph}>
      {segs.map((seg, i) => (
        <Text key={i} style={seg.bold ? S.bold : seg.italic ? S.italic : {}}>
          {seg.text}
        </Text>
      ))}
    </Text>
  );
}

// Same but uses bulletText style (no left margin — parent View handles indent).
function BulletLine({ text }: { text: string }) {
  const segs = parseInline(text);

  if (segs.length === 1 && !segs[0].bold && !segs[0].italic) {
    return <Text style={S.bulletText}>{text}</Text>;
  }

  return (
    <Text style={S.bulletText}>
      {segs.map((seg, i) => (
        <Text key={i} style={seg.bold ? S.bold : seg.italic ? S.italic : {}}>
          {seg.text}
        </Text>
      ))}
    </Text>
  );
}

// ---------------------------------------------------------------------------
// Table helpers
// ---------------------------------------------------------------------------

function parseTableCells(line: string): string[] {
  const trimmed = line.trim();
  // Strip leading/trailing pipe then split on inner pipes
  const inner = trimmed.startsWith("|") ? trimmed.slice(1) : trimmed;
  const stripped = inner.endsWith("|") ? inner.slice(0, -1) : inner;
  return stripped.split("|").map((c) => c.trim());
}

function isSeparatorRow(cells: string[]): boolean {
  return cells.every((c) => /^[-:]+$/.test(c.trim()));
}

function TableBlock({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <View style={S.tableWrapper}>
      <View style={S.tableHeaderRow}>
        {headers.map((h, i) => (
          <Text key={i} style={S.tableCellHeader}>{h}</Text>
        ))}
      </View>
      {rows.map((row, ri) => (
        <View key={ri} style={S.tableRow}>
          {row.map((cell, ci) => (
            <Text key={ci} style={S.tableCell}>{cell}</Text>
          ))}
        </View>
      ))}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Block markdown renderer
// ---------------------------------------------------------------------------

function MarkdownContent({ text }: { text: string }) {
  const lines = text.split("\n");
  const els: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const raw = lines[i];
    const t = raw.trim();

    if (!t) { i++; continue; }

    // Table: one or more consecutive lines that start with |
    if (t.startsWith("|")) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        tableLines.push(lines[i].trim());
        i++;
      }
      const allRows = tableLines.map(parseTableCells);
      const headers = allRows[0] ?? [];
      const dataRows = allRows.slice(1).filter((r) => !isSeparatorRow(r));
      els.push(<TableBlock key={`tbl-${i}`} headers={headers} rows={dataRows} />);
      continue;
    }

    if (/^#{1,3}\s/.test(t)) {
      els.push(<Text key={i} style={S.subheading}>{t.replace(/^#+\s/, "")}</Text>);
    } else if (/^[-*]\s/.test(t)) {
      els.push(
        <View key={i} style={S.bulletRow}>
          <View style={S.bulletDotWrapper}>
            <Text style={S.bulletDot}>•</Text>
          </View>
          <BulletLine text={t.slice(2)} />
        </View>,
      );
    } else {
      els.push(<ParagraphLine key={i} text={t} />);
    }

    i++;
  }

  return <View>{els}</View>;
}

// ---------------------------------------------------------------------------
// Document
// ---------------------------------------------------------------------------

export function ResearchPdfDocument({ title, sections, completedOrders, svgCaptures }: Props) {
  return (
    <Document>
      <Page size="A4" style={S.page}>
        <Text style={S.question}>{title}</Text>

        {sections.map((section, i) => (
          <View key={i}>
            {i > 0 && <View style={S.divider} />}
            <Text style={S.sectionTitle}>{section.title}</Text>
            <MarkdownContent text={section.content} />
          </View>
        ))}

        {completedOrders.length > 0 && (
          <View>
            {sections.length > 0 && <View style={S.divider} />}
            <Text style={S.chartsHeading}>Survey Results</Text>
            {completedOrders.map((order) => {
              const src = svgCaptures.get(order.order_id);
              if (!src) return null;
              return (
                <View key={order.order_id} style={S.chartBlock}>
                  <Text style={S.chartQuestion}>{order.question}</Text>
                  <Image style={S.chartImage} src={src} />
                </View>
              );
            })}
          </View>
        )}

        <Text
          style={S.footer}
          render={({ pageNumber, totalPages }) => `${pageNumber} / ${totalPages}`}
          fixed
        />
      </Page>
    </Document>
  );
}
