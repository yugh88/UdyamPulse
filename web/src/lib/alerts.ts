/** The early-warning agent's next-best action as one plain sentence an RM can act on. */
const NEXT_STEP_SENTENCE: Record<string, string> = {
  visit: "Visit the factory this week to see what changed.",
  call: "Call the owner this week to understand what changed.",
  "limit review": "Review the credit limit against the latest numbers.",
  "visit + limit review": "Visit the factory this week and review the credit limit.",
  restructure: "Talk to the owner about restructuring before a payment is missed.",
  "no action": "No action needed now. Keep watching the signals.",
};

export function nextStepSentence(action: string | null | undefined): string {
  if (!action) return "";
  return NEXT_STEP_SENTENCE[action] ?? `${action.charAt(0).toUpperCase()}${action.slice(1)}.`;
}
