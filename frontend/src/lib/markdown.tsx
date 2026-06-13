import React from 'react';

/*
 * Lightweight markdown renderer — no dependencies.
 * Handles: headings, bold, italic, inline code, code blocks,
 *          unordered + ordered lists, blockquotes, hr, tables, links.
 */

interface Token {
  type: string;
  content: string;
  level?: number;
  ordered?: boolean;
  items?: string[];
  // table-specific
  headers?: string[];
  rows?: string[][];
}

function tokenize(md: string): Token[] {
  const tokens: Token[] = [];
  const lines = md.split('\n');
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Fenced code block
    if (line.startsWith('```')) {
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith('```')) {
        codeLines.push(lines[i]);
        i++;
      }
      tokens.push({ type: 'code', content: codeLines.join('\n') });
      i++;
      continue;
    }

    // Heading
    const headingMatch = line.match(/^(#{1,3})\s+(.+)/);
    if (headingMatch) {
      tokens.push({ type: 'heading', content: headingMatch[2], level: headingMatch[1].length });
      i++;
      continue;
    }

    // HR
    if (/^[-*_]{3,}$/.test(line.trim())) {
      tokens.push({ type: 'hr', content: '' });
      i++;
      continue;
    }

    // Blockquote
    if (line.startsWith('> ')) {
      tokens.push({ type: 'blockquote', content: line.slice(2) });
      i++;
      continue;
    }

    // Table — detect by pipe character pattern
    // A table requires: header row | separator row (---|---) | data rows
    if (line.includes('|') && i + 1 < lines.length) {
      const nextLine = lines[i + 1] ?? '';
      const isSeparator = /^\|?[\s|:\-]+\|[\s|:\-]*$/.test(nextLine.trim());
      if (isSeparator) {
        const headers = _parseCells(line);
        i += 2; // skip header + separator
        const rows: string[][] = [];
        while (i < lines.length && lines[i].includes('|')) {
          const row = _parseCells(lines[i]);
          if (row.length > 0) rows.push(row);
          i++;
        }
        tokens.push({ type: 'table', content: '', headers, rows });
        continue;
      }
    }

    // Unordered list
    if (/^[-*+]\s/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*+]\s/.test(lines[i])) {
        items.push(lines[i].replace(/^[-*+]\s/, ''));
        i++;
      }
      tokens.push({ type: 'ul', content: '', items, ordered: false });
      continue;
    }

    // Ordered list
    if (/^\d+\.\s/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\.\s/.test(lines[i])) {
        items.push(lines[i].replace(/^\d+\.\s/, ''));
        i++;
      }
      tokens.push({ type: 'ol', content: '', items, ordered: true });
      continue;
    }

    // Blank line
    if (line.trim() === '') {
      tokens.push({ type: 'blank', content: '' });
      i++;
      continue;
    }

    // Paragraph — collect consecutive non-special lines
    const paraLines: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() !== '' &&
      !lines[i].startsWith('#') &&
      !lines[i].startsWith('```') &&
      !lines[i].startsWith('> ') &&
      !/^[-*+]\s/.test(lines[i]) &&
      !/^\d+\.\s/.test(lines[i]) &&
      !/^[-*_]{3,}$/.test(lines[i].trim()) &&
      // Don't absorb a table header into a paragraph
      !(lines[i].includes('|') && i + 1 < lines.length && /^\|?[\s|:\-]+\|[\s|:\-]*$/.test((lines[i + 1] ?? '').trim()))
    ) {
      paraLines.push(lines[i]);
      i++;
    }
    if (paraLines.length > 0) {
      tokens.push({ type: 'paragraph', content: paraLines.join(' ') });
    }
  }

  return tokens;
}

function _parseCells(line: string): string[] {
  return line
    .split('|')
    .map(c => c.trim())
    .filter((c, idx, arr) => !(idx === 0 && c === '') && !(idx === arr.length - 1 && c === ''));
}

function renderInline(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  let remaining = text;
  let key = 0;

  while (remaining.length > 0) {
    // Link: [text](url)
    const linkMatch = remaining.match(/^(.*?)\[([^\]]+)\]\(([^)]+)\)([\s\S]*)/);
    // Inline code
    const codeMatch = remaining.match(/^(.*?)`([^`]+)`([\s\S]*)/);
    // Bold
    const boldMatch = remaining.match(/^(.*?)\*\*([^*]+)\*\*([\s\S]*)/);
    // Italic (single *, but not **)
    const italicMatch = remaining.match(/^(.*?)(?<!\*)\*(?!\*)([^*]+)(?<!\*)\*(?!\*)([\s\S]*)/);

    const candidates = [
      linkMatch   ? { idx: linkMatch[1].length,   match: linkMatch,   type: 'link'   } : null,
      codeMatch   ? { idx: codeMatch[1].length,   match: codeMatch,   type: 'code'   } : null,
      boldMatch   ? { idx: boldMatch[1].length,   match: boldMatch,   type: 'bold'   } : null,
      italicMatch ? { idx: italicMatch[1].length, match: italicMatch, type: 'italic' } : null,
    ].filter(Boolean) as { idx: number; match: RegExpMatchArray; type: string }[];

    if (candidates.length === 0) {
      parts.push(<React.Fragment key={key++}>{remaining}</React.Fragment>);
      break;
    }

    candidates.sort((a, b) => a.idx - b.idx);
    const best = candidates[0];

    if (best.match[1]) {
      parts.push(<React.Fragment key={key++}>{best.match[1]}</React.Fragment>);
    }

    if (best.type === 'link') {
      parts.push(
        <a key={key++} href={best.match[3]} target="_blank" rel="noopener noreferrer">
          {best.match[2]}
        </a>
      );
      remaining = best.match[4];
    } else if (best.type === 'code') {
      parts.push(<code key={key++}>{best.match[2]}</code>);
      remaining = best.match[3];
    } else if (best.type === 'bold') {
      parts.push(<strong key={key++}>{best.match[2]}</strong>);
      remaining = best.match[3];
    } else {
      parts.push(<em key={key++}>{best.match[2]}</em>);
      remaining = best.match[3];
    }
  }

  return parts;
}

export default function Markdown({ content }: { content: string }) {
  const tokens = tokenize(content);
  const elements: React.ReactNode[] = [];
  let key = 0;

  for (const tok of tokens) {
    switch (tok.type) {
      case 'heading': {
        const Tag = `h${tok.level ?? 2}` as 'h1' | 'h2' | 'h3';
        elements.push(<Tag key={key++}>{renderInline(tok.content)}</Tag>);
        break;
      }
      case 'paragraph':
        elements.push(<p key={key++}>{renderInline(tok.content)}</p>);
        break;
      case 'code':
        elements.push(<pre key={key++}><code>{tok.content}</code></pre>);
        break;
      case 'blockquote':
        elements.push(<blockquote key={key++}>{renderInline(tok.content)}</blockquote>);
        break;
      case 'ul':
        elements.push(
          <ul key={key++}>
            {(tok.items ?? []).map((item, i) => (
              <li key={i}>{renderInline(item)}</li>
            ))}
          </ul>
        );
        break;
      case 'ol':
        elements.push(
          <ol key={key++}>
            {(tok.items ?? []).map((item, i) => (
              <li key={i}>{renderInline(item)}</li>
            ))}
          </ol>
        );
        break;
      case 'hr':
        elements.push(<hr key={key++} />);
        break;
      case 'table':
        elements.push(
          <div key={key++} className="md-table-wrap">
            <table className="md-table">
              {tok.headers && tok.headers.length > 0 && (
                <thead>
                  <tr>
                    {tok.headers.map((h, ci) => (
                      <th key={ci}>{renderInline(h)}</th>
                    ))}
                  </tr>
                </thead>
              )}
              <tbody>
                {(tok.rows ?? []).map((row, ri) => (
                  <tr key={ri}>
                    {row.map((cell, ci) => (
                      <td key={ci}>{renderInline(cell)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
        break;
      case 'blank':
        break;
    }
  }

  return <div className="md">{elements}</div>;
}
