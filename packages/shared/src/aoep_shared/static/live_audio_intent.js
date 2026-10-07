// Spoken requests that should move the lesson or the webcam.
// The live voice widget loads this before its own script. Keep it free of
// browser APIs so tests can require() it.
function aoepLiveAudioIntent(text, role) {
  const said = String(text || "")
    .toLowerCase()
    .replace(/['’]/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!said) return null;
  const words = said.split(" ");
  const user = role !== "agent";
  const filler = new Set(
    "please lets ok okay now hey go to the a an can you i want would like show me give us just say do try and we should look at move".split(" ")
  );

  function hit(action, target) {
    return {action: action, target: target || ""};
  }

  // "the next section of the vehicle code..." is a lesson sentence. A request
  // has only a short lead-in, and only a few words after the command.
  function asked(pattern) {
    if (!pattern.test(said)) return false;
    const at = said.search(pattern);
    const before = said.slice(0, at).trim();
    const after = said.slice(at).replace(pattern, "").trim();
    const lead = before ? before.split(" ") : [];
    const trail = after ? after.split(" ").length : 0;
    return lead.every((word) => filler.has(word)) && trail <= 6;
  }

  if (asked(/\b(next|another|different|new)\s+games?\b/) || asked(/\b(switch|change)\s+(?:the\s+)?games?\b/)) {
    return hit("next_game");
  }
  const named = said.match(/\b(?:play|start|try|switch to|change to)\s+(?:the\s+)?([a-z0-9][a-z0-9 ]{0,32}?)\s+game\b/);
  if (named) {
    const at = said.search(/\b(?:play|start|try|switch to|change to)\b/);
    const lead = said.slice(0, Math.max(0, at)).trim();
    const leadWords = lead ? lead.split(" ") : [];
    if (leadWords.length <= 6 && leadWords.every((word) => filler.has(word))) {
      return hit("game", named[1].trim());
    }
  }

  if (asked(/\b(next|another|different)\s+letters?\b/)) return hit("next_letter");
  const letter = said.match(/\bletter\s+([a-z])\b/);
  if (letter && asked(/\bletter\s+[a-z]\b/)) return hit("letter", letter[1]);

  if (asked(/\b(another|different|one more|new)\s+examples?\b/) || asked(/\b(show|give|see)\s+(?:me\s+)?(?:an|another|a)\s+example\b/)) {
    return hit("example");
  }
  if (
    asked(/\b(another|different|new)\s+(?:animations?|pictures?|videos?)\b/)
    || asked(/\b(change|switch)\s+(?:the\s+)?animations?\b/)
    || asked(/\bshow\s+(?:me\s+)?(?:the\s+)?animation\b/)
  ) {
    return hit("animation");
  }
  if (asked(/\b(next|another)\s+(section|slide|part|page|lesson)\b/)) return hit("next_section");
  if (user && words.length <= 6 && /^(next|go on|move on|keep going|continue|next one)$/.test(said)) {
    return hit("next");
  }
  if (asked(/\b(lets|please)\s+(continue|move on|go on|keep going)\b/)) return hit("next");
  return null;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {aoepLiveAudioIntent: aoepLiveAudioIntent};
}
