// Species banks for zoo / reef arcade games — real animals & fish to memorize.

export type Age = "kids" | "tween" | "teen" | "adult";

export type Species = {
  id: string;
  emoji: string;
  name: string;
  scientific?: string;
  habitat: string;
  clue: string;
  group: "mammal" | "bird" | "reptile" | "amphibian" | "fish" | "invertebrate";
};

export const ZOO_SPECIES: Record<Age, Species[]> = {
  kids: [
    { id: "lion", emoji: "🦁", name: "Lion", habitat: "African savanna", clue: "King of the jungle — roars loudly", group: "mammal" },
    { id: "elephant", emoji: "🐘", name: "Elephant", habitat: "Grasslands & forests", clue: "Biggest land animal — has a trunk", group: "mammal" },
    { id: "giraffe", emoji: "🦒", name: "Giraffe", habitat: "African savanna", clue: "Tallest animal — eats leaves from tall trees", group: "mammal" },
    { id: "zebra", emoji: "🦓", name: "Zebra", habitat: "African plains", clue: "Black and white stripes", group: "mammal" },
    { id: "panda", emoji: "🐼", name: "Giant Panda", habitat: "Bamboo forests", clue: "Black and white bear — eats bamboo", group: "mammal" },
    { id: "monkey", emoji: "🐒", name: "Monkey", habitat: "Tropical forests", clue: "Swings from tree to tree", group: "mammal" },
    { id: "penguin", emoji: "🐧", name: "Penguin", habitat: "Antarctica & coasts", clue: "Bird that swims but cannot fly", group: "bird" },
    { id: "parrot", emoji: "🦜", name: "Parrot", habitat: "Rainforests", clue: "Colorful bird that can mimic speech", group: "bird" },
    { id: "snake", emoji: "🐍", name: "Snake", habitat: "Many habitats", clue: "Slithers — no legs", group: "reptile" },
    { id: "frog", emoji: "🐸", name: "Frog", habitat: "Ponds & wetlands", clue: "Hops and says 'ribbit'", group: "amphibian" },
  ],
  tween: [
    { id: "cheetah", emoji: "🐆", name: "Cheetah", habitat: "African savanna", clue: "Fastest land animal — spotted coat", group: "mammal" },
    { id: "koala", emoji: "🐨", name: "Koala", habitat: "Australian eucalyptus", clue: "Marsupial that sleeps in trees", group: "mammal" },
    { id: "kangaroo", emoji: "🦘", name: "Kangaroo", habitat: "Australian outback", clue: "Hops on powerful hind legs — has a pouch", group: "mammal" },
    { id: "polar_bear", emoji: "🐻‍❄️", name: "Polar Bear", habitat: "Arctic ice", clue: "White bear — world's largest carnivore on land", group: "mammal" },
    { id: "rhino", emoji: "🦏", name: "Rhinoceros", habitat: "Grasslands", clue: "Heavy animal with a horn on its nose", group: "mammal" },
    { id: "hippo", emoji: "🦛", name: "Hippopotamus", habitat: "African rivers", clue: "Spends days in water — very dangerous", group: "mammal" },
    { id: "eagle", emoji: "🦅", name: "Bald Eagle", habitat: "North America", clue: "National bird of the USA — sharp talons", group: "bird" },
    { id: "owl", emoji: "🦉", name: "Owl", habitat: "Forests worldwide", clue: "Nocturnal hunter — rotates head far", group: "bird" },
    { id: "crocodile", emoji: "🐊", name: "Crocodile", habitat: "Tropical rivers", clue: "Armored reptile with powerful jaws", group: "reptile" },
    { id: "turtle", emoji: "🐢", name: "Sea Turtle", habitat: "Oceans & beaches", clue: "Reptile with a hard shell — returns to lay eggs", group: "reptile" },
    { id: "bat", emoji: "🦇", name: "Bat", habitat: "Caves & forests", clue: "Only mammal that truly flies", group: "mammal" },
    { id: "wolf", emoji: "🐺", name: "Gray Wolf", habitat: "Forests & tundra", clue: "Pack hunter — ancestor of dogs", group: "mammal" },
  ],
  teen: [
    { id: "orangutan", emoji: "🦧", name: "Orangutan", scientific: "Pongo", habitat: "Borneo & Sumatra", clue: "Great ape — 'person of the forest' in Malay", group: "mammal" },
    { id: "gorilla", emoji: "🦍", name: "Gorilla", scientific: "Gorilla gorilla", habitat: "Central African forests", clue: "Largest living primate — gentle herbivore", group: "mammal" },
    { id: "sloth", emoji: "🦥", name: "Three-toed Sloth", scientific: "Bradypus", habitat: "Central/South American canopy", clue: "Moves very slowly — algae grows on its fur", group: "mammal" },
    { id: "platypus", emoji: "🫏", name: "Platypus", scientific: "Ornithorhynchus", habitat: "Eastern Australia streams", clue: "Egg-laying mammal with a duck bill", group: "mammal" },
    { id: "flamingo", emoji: "🦩", name: "Flamingo", scientific: "Phoenicopterus", habitat: "Shallow lagoons", clue: "Pink from shrimp diet — stands on one leg", group: "bird" },
    { id: "peacock", emoji: "🦚", name: "Peacock", scientific: "Pavo cristatus", habitat: "South Asian forests", clue: "Male displays iridescent tail feathers", group: "bird" },
    { id: "komodo", emoji: "🐉", name: "Komodo Dragon", scientific: "Varanus komodoensis", habitat: "Indonesian islands", clue: "Largest living lizard — venomous bite", group: "reptile" },
    { id: "chameleon", emoji: "🦎", name: "Chameleon", scientific: "Chamaeleonidae", habitat: "Madagascar & Africa", clue: "Changes color — eyes move independently", group: "reptile" },
    { id: "salamander", emoji: "🦎", name: "Salamander", scientific: "Caudata", habitat: "Moist woodlands", clue: "Amphibian — some species regenerate limbs", group: "amphibian" },
    { id: "red_panda", emoji: "🐾", name: "Red Panda", scientific: "Ailurus fulgens", habitat: "Himalayan bamboo", clue: "Not a true panda — arboreal bamboo eater", group: "mammal" },
  ],
  adult: [
    { id: "axolotl", emoji: "🦎", name: "Axolotl", scientific: "Ambystoma mexicanum", habitat: "Lake Xochimilco, Mexico", clue: "Paedomorphic salamander — can regenerate brain", group: "amphibian" },
    { id: "tapir", emoji: "🐗", name: "Malayan Tapir", scientific: "Tapirus indicus", habitat: "Southeast Asian rainforest", clue: "Black front, white back — odd-toed ungulate", group: "mammal" },
    { id: "okapi", emoji: "🦓", name: "Okapi", scientific: "Okapia johnstoni", habitat: "Congo rainforest", clue: "Forest giraffe — zebra-striped legs", group: "mammal" },
    { id: "cassowary", emoji: "🦤", name: "Cassowary", scientific: "Casuarius", habitat: "New Guinea & Australia", clue: "Flightless bird — dangerous casque and claws", group: "bird" },
    { id: "tuatara", emoji: "🦎", name: "Tuatara", scientific: "Sphenodon", habitat: "New Zealand", clue: "Living fossil — not a true lizard", group: "reptile" },
    { id: "pangolin", emoji: "🦔", name: "Pangolin", scientific: "Manis", habitat: "Africa & Asia", clue: "Only mammal covered in keratin scales", group: "mammal" },
    { id: "wombat", emoji: "🐻", name: "Wombat", scientific: "Vombatus", habitat: "Australian scrub", clue: "Marsupial — cube-shaped droppings", group: "mammal" },
    { id: "manatee", emoji: "🦭", name: "Manatee", scientific: "Trichechus", habitat: "Warm coastal waters", clue: "Gentle sea cow — grazes on seagrass", group: "mammal" },
  ],
};

export const REEF_SPECIES: Record<Age, Species[]> = {
  kids: [
    { id: "clownfish", emoji: "🐠", name: "Clownfish", habitat: "Coral reef anemones", clue: "Orange with white stripes — lives in anemones", group: "fish" },
    { id: "pufferfish", emoji: "🐡", name: "Pufferfish", habitat: "Tropical reefs", clue: "Inflates like a balloon when scared", group: "fish" },
    { id: "starfish", emoji: "⭐", name: "Starfish", habitat: "Rocky shores & reefs", clue: "Five arms — can regenerate lost arms", group: "invertebrate" },
    { id: "jellyfish", emoji: "🪼", name: "Jellyfish", habitat: "Open ocean", clue: "Drifts with tentacles — can sting", group: "invertebrate" },
    { id: "dolphin", emoji: "🐬", name: "Dolphin", habitat: "Oceans worldwide", clue: "Smart marine mammal — uses echolocation", group: "mammal" },
    { id: "whale", emoji: "🐋", name: "Blue Whale", habitat: "Open ocean", clue: "Largest animal ever — eats tiny krill", group: "mammal" },
    { id: "shark", emoji: "🦈", name: "Shark", habitat: "Oceans", clue: "Cartilage skeleton — rows of sharp teeth", group: "fish" },
    { id: "seahorse", emoji: "🐚", name: "Seahorse", habitat: "Seagrass beds", clue: "Male carries the babies in a pouch", group: "fish" },
    { id: "crab", emoji: "🦀", name: "Crab", habitat: "Beaches & reefs", clue: "Walks sideways — hard shell", group: "invertebrate" },
    { id: "octopus", emoji: "🐙", name: "Octopus", habitat: "Coral reefs & rocks", clue: "Eight arms — can change color and shape", group: "invertebrate" },
  ],
  tween: [
    { id: "angelfish", emoji: "🐟", name: "Angelfish", habitat: "Coral reefs", clue: "Flat body with long dorsal fin — bright colors", group: "fish" },
    { id: "parrotfish", emoji: "🐠", name: "Parrotfish", habitat: "Tropical reefs", clue: "Beak-like mouth — helps build sand from coral", group: "fish" },
    { id: "manta", emoji: "🦈", name: "Manta Ray", habitat: "Open ocean", clue: "Huge flat ray — filter feeds on plankton", group: "fish" },
    { id: "stingray", emoji: "🐟", name: "Stingray", habitat: "Sandy seabeds", clue: "Flat body — venomous barb on tail", group: "fish" },
    { id: "lobster", emoji: "🦞", name: "Lobster", habitat: "Rocky ocean floor", clue: "Large claws — nocturnal scavenger", group: "invertebrate" },
    { id: "squid", emoji: "🦑", name: "Squid", habitat: "Open ocean", clue: "Ten arms — shoots ink to escape", group: "invertebrate" },
    { id: "coral", emoji: "🪸", name: "Brain Coral", habitat: "Shallow reefs", clue: "Animal colony — builds reef structure", group: "invertebrate" },
    { id: "sea_urchin", emoji: "🦔", name: "Sea Urchin", habitat: "Rocky reefs", clue: "Spiny round echinoderm — grazes algae", group: "invertebrate" },
    { id: "moray", emoji: "🐍", name: "Moray Eel", habitat: "Reef crevices", clue: "Snake-like fish — hides in coral holes", group: "fish" },
    { id: "nautilus", emoji: "🐚", name: "Nautilus", habitat: "Deep Indo-Pacific", clue: "Living fossil — chambered spiral shell", group: "invertebrate" },
  ],
  teen: [
    { id: "lionfish", emoji: "🐟", name: "Lionfish", scientific: "Pterois", habitat: "Indo-Pacific reefs", clue: "Venomous spines — invasive in Atlantic", group: "fish" },
    { id: "barracuda", emoji: "🐟", name: "Barracuda", scientific: "Sphyraena", habitat: "Tropical seas", clue: "Long predator — sharp teeth, silver body", group: "fish" },
    { id: "grouper", emoji: "🐟", name: "Goliath Grouper", scientific: "Epinephelus", habitat: "Atlantic reefs", clue: "Massive reef fish — can swallow small sharks", group: "fish" },
    { id: "triggerfish", emoji: "🐠", name: "Triggerfish", scientific: "Balistidae", habitat: "Coral reefs", clue: "Locked dorsal spine — aggressive nest defender", group: "fish" },
    { id: "box_jelly", emoji: "🪼", name: "Box Jellyfish", scientific: "Chironex", habitat: "Indo-Pacific", clue: "Most venomous marine animal — cube-shaped bell", group: "invertebrate" },
    { id: "nudibranch", emoji: "🐌", name: "Nudibranch", scientific: "Nudibranchia", habitat: "Reef floors", clue: "Colorful sea slug — stores stinging cells from prey", group: "invertebrate" },
    { id: "cuttlefish", emoji: "🦑", name: "Cuttlefish", scientific: "Sepia", habitat: "Shallow seas", clue: "Masters of camouflage — W-shaped pupils", group: "invertebrate" },
    { id: "hammerhead", emoji: "🦈", name: "Hammerhead Shark", scientific: "Sphyrnidae", habitat: "Warm oceans", clue: "Wide T-shaped head — enhanced stereo vision", group: "fish" },
    { id: "whale_shark", emoji: "🦈", name: "Whale Shark", scientific: "Rhincodon typus", habitat: "Tropical open ocean", clue: "Largest fish — filter feeder with spot pattern", group: "fish" },
    { id: "anemone", emoji: "🌸", name: "Sea Anemone", scientific: "Actiniaria", habitat: "Reef surfaces", clue: "Predatory polyp — symbiotic with clownfish", group: "invertebrate" },
  ],
  adult: [
    { id: "coelacanth", emoji: "🐟", name: "Coelacanth", scientific: "Latimeria", habitat: "Deep Indian Ocean", clue: "Living fossil — lobe-finned fish thought extinct", group: "fish" },
    { id: "oarfish", emoji: "🐍", name: "Oarfish", scientific: "Regalecus", habitat: "Deep ocean", clue: "Longest bony fish — rarely seen alive", group: "fish" },
    { id: "mantis_shrimp", emoji: "🦐", name: "Mantis Shrimp", scientific: "Stomatopoda", habitat: "Tropical reefs", clue: "Punch faster than a bullet — complex color vision", group: "invertebrate" },
    { id: "blobfish", emoji: "🐟", name: "Blobfish", scientific: "Psychrolutes", habitat: "Deep sea", clue: "Gelatinous — looks different at surface pressure", group: "fish" },
    { id: "goblin_shark", emoji: "🦈", name: "Goblin Shark", scientific: "Mitsukurina", habitat: "Deep ocean", clue: "Protrusible jaws — pink skin", group: "fish" },
    { id: "vampire_squid", emoji: "🦑", name: "Vampire Squid", scientific: "Vampyroteuthis", habitat: "Oxygen-minimum zones", clue: "Neither true squid nor octopus — bioluminescent", group: "invertebrate" },
    { id: "leafy_seadragon", emoji: "🐉", name: "Leafy Seadragon", scientific: "Phycodurus", habitat: "Southern Australia", clue: "Camouflaged like kelp — related to seahorses", group: "fish" },
    { id: "architeuthis", emoji: "🦑", name: "Giant Squid", scientific: "Architeuthis", habitat: "Deep ocean", clue: "Largest invertebrate — battles sperm whales", group: "invertebrate" },
  ],
};

/** Pick 4 options including the correct species name. */
export function quizOptions(correct: Species, pool: Species[]): string[] {
  const names = new Set<string>([correct.name]);
  const shuffled = [...pool].filter((s) => s.id !== correct.id).sort(() => Math.random() - 0.5);
  for (const s of shuffled) {
    if (names.size >= 4) break;
    names.add(s.name);
  }
  while (names.size < 4) names.add(`Unknown ${names.size}`);
  return [...names].sort(() => Math.random() - 0.5);
}
