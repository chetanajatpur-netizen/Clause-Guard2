# design.md - ClauseGuard UI

Feel: clean, trustworthy, legal-tech SaaS. Light theme default. Lots of whitespace, rounded cards, subtle shadows.

## Colors (put in `styles/tokens.css` as CSS variables)
| Token | Hex | Use |
|---|---|---|
| --bg | #F7F8FC | page background |
| --surface | #FFFFFF | cards |
| --border | #E4E7EF | card borders |
| --text | #1B1F3B | main text |
| --text-muted | #6B7094 | secondary text |
| --primary | #4F46E5 | buttons, links, active nav |
| --primary-hover | #4338CA | hover |
| --risk-high | #DC2626 (bg #FEE2E2) | High risk |
| --risk-medium | #D97706 (bg #FEF3C7) | Medium risk |
| --risk-low | #059669 (bg #D1FAE5) | Low risk |
| --neutral-chip | #E5E7EB | "No Clause" |

## Fonts
- Headings + body: **Inter** (Google Fonts), fallback `system-ui, sans-serif`
- Code / confidence numbers: **JetBrains Mono**, fallback `monospace`

## Typography scale
| Role | Size | Weight |
|---|---|---|
| H1 | 32px | 700 |
| H2 | 24px | 600 |
| H3 | 18px | 600 |
| Body | 16px | 400 |
| Small / meta | 13px | 500 |

## Layout
- Left sidebar (Analyze, History, Insights) collapsing to top bar under 768px
- Content max-width 1100px, 24px gutters, card radius 12px, 16px/24px padding
- Analyze page: upload card on top -> summary strip (overall risk, counts per risk level) -> search bar -> clause list
- ClauseCard: left color bar by risk, clause-type chip, RiskBadge, confidence (mono), expandable full text

## States (all required)
- Loading: skeleton or spinner with text "Analyzing contract..."
- Error: red-tinted banner with message + retry
- Empty: friendly illustration-free text + CTA
- Footer disclaimer on every page: "ClauseGuard is an educational tool and not legal advice."
