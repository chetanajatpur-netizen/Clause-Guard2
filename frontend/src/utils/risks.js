/**
 * Shared utility for extracting risky / flagged clauses.
 * Single source of truth for constructing the Risks list.
 */
export function getRiskyClauses(clauses) {
  if (!clauses || !Array.isArray(clauses)) return [];
  return clauses.filter((c) => Boolean(c.flagged));
}

export function getUnflaggedClauses(clauses) {
  if (!clauses || !Array.isArray(clauses)) return [];
  return clauses.filter((c) => !c.flagged);
}
