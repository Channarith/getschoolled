// Professional course scenarios — "What would you do?" workplace decision drills.
// Mirrors corporate training tracks (Compliance, Safety, Privacy, etc.).

export type ProTrack =
  | "compliance"
  | "safety"
  | "privacy"
  | "ethics"
  | "security"
  | "trade";

export type ProScenario = {
  id: string;
  track: ProTrack;
  title: string;
  setup: string;
  prompt: string;
  options: string[];
  answer: number;
  explain: string;
  policy?: string;
};

export const TRACK_LABELS: Record<ProTrack, string> = {
  compliance: "Compliance",
  safety: "Safety",
  privacy: "Privacy & Data",
  ethics: "Ethics & Conduct",
  security: "Security",
  trade: "Trade & Export",
};

export const PRO_SCENARIOS: ProScenario[] = [
  // --- Compliance ---------------------------------------------------------- //
  {
    id: "comp_01", track: "compliance", title: "Gift from a vendor",
    setup: "A supplier invites you to a luxury box at a championship game. Tickets are worth $800 each.",
    prompt: "What would you do?",
    options: ["Accept — it's relationship building", "Decline or check your gifts & entertainment policy first", "Accept but don't tell your manager", "Ask the vendor to give tickets to your family instead"],
    answer: 1,
    explain: "Many policies cap or prohibit high-value gifts. Always check before accepting.",
    policy: "Gifts & entertainment policy",
  },
  {
    id: "comp_02", track: "compliance", title: "Suspected bribery",
    setup: "An overseas agent says a 'facilitation payment' is required to release your shipment from customs.",
    prompt: "What would you do?",
    options: ["Pay in cash to avoid delays", "Refuse and escalate to compliance/legal immediately", "Ask a colleague to pay so it's not on your record", "Ignore and hope it clears"],
    answer: 1,
    explain: "Facilitation payments may violate anti-bribery laws (FCPA, UK Bribery Act). Escalate — never pay on your own.",
    policy: "Anti-bribery & corruption",
  },
  {
    id: "comp_03", track: "compliance", title: "Conflicts of interest",
    setup: "You're asked to evaluate vendors. Your sibling works for one of the bidders.",
    prompt: "What would you do?",
    options: ["Proceed — you can stay objective", "Disclose the conflict and recuse yourself from that decision", "Favor their company to help family", "Quit the committee silently"],
    answer: 1,
    explain: "Disclose conflicts early. Recusal protects you and the organization.",
    policy: "Conflict of interest",
  },
  // --- Safety -------------------------------------------------------------- //
  {
    id: "safe_01", track: "safety", title: "Blocked fire exit",
    setup: "You find pallets stacked in front of an emergency exit in the warehouse.",
    prompt: "What would you do?",
    options: ["Leave it — someone else will fix it", "Clear it yourself if safe, and report to facilities/safety", "Use the exit anyway in an emergency", "Wait until the next safety audit"],
    answer: 1,
    explain: "Blocked exits kill people in fires. Clear and report immediately.",
    policy: "OSHA / fire safety",
  },
  {
    id: "safe_02", track: "safety", title: "Chemical spill",
    setup: "A coworker knocks over a bottle of cleaning solvent. The area smells strong; no one is hurt yet.",
    prompt: "What would you do?",
    options: ["Mop it up quickly without telling anyone", "Alert others, ventilate, use spill kit per SDS, and notify supervisor", "Ignore — it will evaporate", "Throw paper towels in the regular trash"],
    answer: 1,
    explain: "Follow SDS/spill procedures. Ventilate, contain, label waste, notify supervisor.",
    policy: "Lab / chemical safety",
  },
  {
    id: "safe_03", track: "safety", title: "Forklift near pedestrians",
    setup: "A forklift operator is driving fast through a pedestrian walkway while people are nearby.",
    prompt: "What would you do?",
    options: ["Say nothing — not your job", "Stop work if needed and report to supervisor/safety", "Walk closer to save time", "Film it for social media"],
    answer: 1,
    explain: "Pedestrian-vehicle separation saves lives. Speak up and report unsafe acts.",
    policy: "Forklift / pedestrian safety",
  },
  // --- Privacy ------------------------------------------------------------- //
  {
    id: "priv_01", track: "privacy", title: "Patient list on screen",
    setup: "You walk past a clinic workstation. A patient schedule is visible to everyone in the hallway.",
    prompt: "What would you do?",
    options: ["Read the names to see if you know anyone", "Notify staff to lock the screen / reposition monitor", "Take a photo for training", "Ignore — it's their problem"],
    answer: 1,
    explain: "PHI must not be exposed. Prompt staff to apply minimum-necessary and screen privacy.",
    policy: "HIPAA / PHI handling",
  },
  {
    id: "priv_02", track: "privacy", title: "Email with SSN",
    setup: "A colleague emails you a spreadsheet with employee Social Security numbers to 'fix a typo.'",
    prompt: "What would you do?",
    options: ["Reply-all with the corrected file", "Use a secure channel, minimize data, and ask if SSNs are necessary", "Forward to your personal email to work offline", "Delete and forget"],
    answer: 1,
    explain: "SSNs are sensitive PII. Use secure tools, limit recipients, and question whether full SSNs are needed.",
    policy: "Data privacy workplace",
  },
  {
    id: "priv_03", track: "privacy", title: "Lost USB drive",
    setup: "You find a USB drive in the parking lot labeled 'Q4 payroll.'",
    prompt: "What would you do?",
    options: ["Plug it into your laptop to find the owner", "Turn it in to IT/security without accessing contents", "Keep it until someone asks", "Throw it away"],
    answer: 1,
    explain: "Unknown USB devices may contain malware or sensitive data. Hand to IT/security unopened.",
    policy: "Data privacy / device security",
  },
  // --- Ethics -------------------------------------------------------------- //
  {
    id: "eth_01", track: "ethics", title: "Harassment overheard",
    setup: "You hear a manager make repeated unwelcome comments to a junior employee who looks uncomfortable.",
    prompt: "What would you do?",
    options: ["Ignore — not your business", "Check in with the colleague if safe, and report via HR/ethics hotline", "Confront publicly on social media", "Laugh along to fit in"],
    answer: 1,
    explain: "Support the target if appropriate, document facts, and use official reporting channels.",
    policy: "Sexual harassment prevention",
  },
  {
    id: "eth_02", track: "ethics", title: "Pressure to falsify records",
    setup: "Your supervisor asks you to backdate a safety inspection log before an auditor arrives tomorrow.",
    prompt: "What would you do?",
    options: ["Do it — they're your boss", "Refuse and report through ethics/compliance channels", "Backdate only some entries", "Quit on the spot without reporting"],
    answer: 1,
    explain: "Falsifying records is fraud and puts people at risk. Refuse and escalate.",
    policy: "Workplace ethics",
  },
  {
    id: "eth_03", track: "ethics", title: "Social media post",
    setup: "A coworker posts confidential project screenshots on LinkedIn with the company logo visible.",
    prompt: "What would you do?",
    options: ["Like the post to be supportive", "Ask them to remove it and notify manager/comms if needed", "Repost to your network", "Screenshot and share externally"],
    answer: 1,
    explain: "Confidential work product must not be shared publicly. Prompt removal and escalate if necessary.",
    policy: "Social media at work",
  },
  // --- Security ------------------------------------------------------------ //
  {
    id: "sec_01", track: "security", title: "Phishing email",
    setup: "You receive an urgent email: 'Password expires in 1 hour — click here to reset.' The link goes to an unfamiliar domain.",
    prompt: "What would you do?",
    options: ["Click and enter your password quickly", "Report as phishing and use official password portal only", "Forward to all colleagues as a warning with the link", "Reply asking if it's real"],
    answer: 1,
    explain: "Verify via official channels. Report phishing to IT/security — don't click suspicious links.",
    policy: "Security awareness",
  },
  {
    id: "sec_02", track: "security", title: "Tailgating at badge reader",
    setup: "Someone without a badge follows you through a secure door saying they 'forgot their card.'",
    prompt: "What would you do?",
    options: ["Hold the door — be polite", "Require them to badge in or escort to reception/security", "Let them in if they look like an employee", "Ignore and keep walking"],
    answer: 1,
    explain: "Tailgating defeats physical security. Everyone badges individually or uses visitor process.",
    policy: "Security policies",
  },
  {
    id: "sec_03", track: "security", title: "Ransomware pop-up",
    setup: "Your screen shows a pop-up: files encrypted, pay Bitcoin in 24 hours. A coworker says to pay quietly.",
    prompt: "What would you do?",
    options: ["Pay from petty cash", "Disconnect from network, do not pay, call IT/security immediately", "Restart and hope it goes away", "Email the attacker for a discount"],
    answer: 1,
    explain: "Isolate the device, preserve evidence, invoke incident response. Paying encourages crime and may not restore data.",
    policy: "Cyber incident response",
  },
  // --- Trade --------------------------------------------------------------- //
  {
    id: "trade_01", track: "trade", title: "Export classification question",
    setup: "A customer in another country wants your product's technical drawings sent by email tonight.",
    prompt: "What would you do?",
    options: ["Send immediately to close the deal", "Verify export classification and license requirements first", "Send a blurry photo instead", "Ask the customer to classify it"],
    answer: 1,
    explain: "Technical data may require export authorization. Compliance review before release.",
    policy: "Export control (US regulations)",
  },
  {
    id: "trade_02", track: "trade", title: "Sanctioned country inquiry",
    setup: "A prospect from a country under trade sanctions requests pricing and shipment terms.",
    prompt: "What would you do?",
    options: ["Quote quickly before competitors do", "Stop and consult trade compliance — do not proceed without clearance", "Ship through a third country secretly", "Ignore the inquiry"],
    answer: 1,
    explain: "Sanctions violations carry severe penalties. Trade compliance must screen every deal.",
    policy: "Trade compliance basics",
  },
];

export function scenariosForTrack(track: ProTrack | "all"): ProScenario[] {
  if (track === "all") return [...PRO_SCENARIOS];
  return PRO_SCENARIOS.filter((s) => s.track === track);
}
