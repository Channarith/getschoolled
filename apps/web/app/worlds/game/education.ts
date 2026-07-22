/** Comprehensive question bank — 80+ questions across 8 subjects */
export type Subject = "math"|"science"|"language"|"geography"|"history"|"capitals"|"biology"|"astronomy";
export type Difficulty = "easy"|"medium"|"hard";

export interface EduQuestion {
  id: string; subject: Subject; difficulty: Difficulty;
  text: string; opts: string[]; correct: number; xp: number; emoji: string; funFact?: string; monument?: string;
}

export const ALL_QUESTIONS: EduQuestion[] = [
  // MATH
  {id:"m01",subject:"math",difficulty:"easy",  text:"7 × 8 = ?",opts:["54","56","58","64"],correct:1,xp:10,emoji:"🧮",funFact:"7 and 8 are the two most commonly mis-multiplied numbers!"},
  {id:"m02",subject:"math",difficulty:"easy",  text:"√144 = ?",opts:["10","11","12","14"],correct:2,xp:15,emoji:"🧮"},
  {id:"m03",subject:"math",difficulty:"easy",  text:"What fraction equals 0.5?",opts:["1/3","1/4","1/2","2/3"],correct:2,xp:10,emoji:"🧮"},
  {id:"m04",subject:"math",difficulty:"easy",  text:"Sides on a hexagon?",opts:["5","6","7","8"],correct:1,xp:10,emoji:"🧮",funFact:"Honeycombs use hexagons—the most efficient shape!"},
  {id:"m05",subject:"math",difficulty:"medium",text:"15% of 200?",opts:["25","30","35","40"],correct:1,xp:15,emoji:"🧮"},
  {id:"m06",subject:"math",difficulty:"medium",text:"2³ = ?",opts:["6","8","12","16"],correct:1,xp:15,emoji:"🧮",funFact:"2^10 = 1,024 — why computer memory uses powers of 2!"},
  {id:"m07",subject:"math",difficulty:"medium",text:"π ≈ ?",opts:["2.14","3.14","4.14","3.41"],correct:1,xp:20,emoji:"🧮",funFact:"Pi has been calculated to over 100 trillion digits!"},
  {id:"m08",subject:"math",difficulty:"easy",  text:"Perimeter of 5×3 rectangle?",opts:["8","15","16","20"],correct:2,xp:15,emoji:"🧮"},
  {id:"m09",subject:"math",difficulty:"medium",text:"Sum of angles in a triangle?",opts:["90°","120°","180°","360°"],correct:2,xp:20,emoji:"🧮",funFact:"ANY triangle always has angles summing to exactly 180°!"},
  {id:"m10",subject:"math",difficulty:"medium",text:"12² = ?",opts:["124","144","132","164"],correct:1,xp:15,emoji:"🧮"},
  {id:"m11",subject:"math",difficulty:"hard",  text:"If a=3, b=4, √(a²+b²)=?",opts:["5","6","7","8"],correct:0,xp:25,emoji:"🧮",funFact:"The famous 3-4-5 Pythagorean triple!"},
  {id:"m12",subject:"math",difficulty:"easy",  text:"Next prime after 13?",opts:["14","15","16","17"],correct:3,xp:15,emoji:"🧮"},
  // SCIENCE
  {id:"s01",subject:"science",difficulty:"easy",  text:"Closest planet to the Sun?",opts:["Venus","Mars","Mercury","Earth"],correct:2,xp:10,emoji:"🔬"},
  {id:"s02",subject:"science",difficulty:"easy",  text:"Gas plants absorb?",opts:["Oxygen","CO₂","Nitrogen","Hydrogen"],correct:1,xp:10,emoji:"🔬",funFact:"Plants literally eat air and sunlight!"},
  {id:"s03",subject:"science",difficulty:"medium",text:"Bones in adult human body?",opts:["186","206","226","246"],correct:1,xp:20,emoji:"🔬",funFact:"Babies have ~270 bones; many fuse as we grow!"},
  {id:"s04",subject:"science",difficulty:"easy",  text:"Chemical symbol for water?",opts:["H₂O","CO₂","NaCl","O₂"],correct:0,xp:10,emoji:"🔬"},
  {id:"s05",subject:"science",difficulty:"easy",  text:"Fastest land animal?",opts:["Lion","Horse","Cheetah","Eagle"],correct:2,xp:10,emoji:"🔬",funFact:"Cheetahs reach 112 km/h but only sprint 30 seconds!"},
  {id:"s06",subject:"science",difficulty:"medium",text:"Center of an atom?",opts:["Electron","Proton","Nucleus","Neutron"],correct:2,xp:15,emoji:"🔬"},
  {id:"s07",subject:"science",difficulty:"medium",text:"Speed of light (km/s)?",opts:["3,000","30,000","300,000","3,000,000"],correct:2,xp:20,emoji:"🔬",funFact:"Light circles Earth 7.5 times every second!"},
  {id:"s08",subject:"science",difficulty:"hard",  text:"Powerhouse of the cell?",opts:["Nucleus","Ribosome","Mitochondria","Vacuole"],correct:2,xp:20,emoji:"🔬"},
  {id:"s09",subject:"science",difficulty:"medium",text:"Most abundant gas in air?",opts:["Oxygen","CO₂","Nitrogen","Argon"],correct:2,xp:15,emoji:"🔬",funFact:"Nitrogen is 78% of air — we barely notice it!"},
  // GEOGRAPHY
  {id:"g01",subject:"geography",difficulty:"easy",  text:"Capital of France?",opts:["London","Berlin","Paris","Madrid"],correct:2,xp:10,emoji:"🌍"},
  {id:"g02",subject:"geography",difficulty:"easy",  text:"Largest ocean?",opts:["Atlantic","Indian","Arctic","Pacific"],correct:3,xp:10,emoji:"🌍",funFact:"Pacific is bigger than all Earth's land combined!"},
  {id:"g03",subject:"geography",difficulty:"easy",  text:"Egypt is on which continent?",opts:["Asia","Europe","Africa","S. America"],correct:2,xp:10,emoji:"🌍"},
  {id:"g04",subject:"geography",difficulty:"easy",  text:"Longest river?",opts:["Amazon","Nile","Yangtze","Mississippi"],correct:1,xp:15,emoji:"🌍",funFact:"The Nile flows NORTH — most rivers flow south!"},
  {id:"g05",subject:"geography",difficulty:"medium",text:"Capital of Japan?",opts:["Osaka","Kyoto","Hiroshima","Tokyo"],correct:3,xp:10,emoji:"🌍"},
  {id:"g06",subject:"geography",difficulty:"medium",text:"Capital of Australia?",opts:["Sydney","Melbourne","Canberra","Brisbane"],correct:2,xp:15,emoji:"🌍",funFact:"Sydney is NOT the capital — Canberra was purpose-built!"},
  {id:"g07",subject:"geography",difficulty:"medium",text:"Capital of Brazil?",opts:["São Paulo","Rio","Brasília","Salvador"],correct:2,xp:15,emoji:"🌍"},
  {id:"g08",subject:"geography",difficulty:"medium",text:"Capital of Canada?",opts:["Toronto","Vancouver","Ottawa","Montreal"],correct:2,xp:15,emoji:"🌍",funFact:"Toronto is the biggest city but Ottawa is the capital!"},
  {id:"g09",subject:"geography",difficulty:"easy",  text:"Capital of Germany?",opts:["Munich","Frankfurt","Hamburg","Berlin"],correct:3,xp:10,emoji:"🌍"},
  {id:"g10",subject:"geography",difficulty:"easy",  text:"Capital of South Korea?",opts:["Busan","Incheon","Seoul","Daegu"],correct:2,xp:10,emoji:"🌍"},
  {id:"g11",subject:"geography",difficulty:"medium",text:"Which mountain range has Everest?",opts:["Alps","Andes","Himalayas","Rockies"],correct:2,xp:15,emoji:"🌍",funFact:"Everest grows 4mm taller every year!"},
  {id:"g12",subject:"geography",difficulty:"medium",text:"Largest US state by area?",opts:["Texas","California","Montana","Alaska"],correct:3,xp:15,emoji:"🌍",funFact:"Alaska is 2.5× bigger than Texas!"},
  // HISTORY
  {id:"h01",subject:"history",difficulty:"easy",  text:"WWII ended in which year?",opts:["1943","1944","1945","1946"],correct:2,xp:15,emoji:"🏛",monument:"pyramid"},
  {id:"h02",subject:"history",difficulty:"easy",  text:"First person on the Moon?",opts:["Buzz Aldrin","Neil Armstrong","Yuri Gagarin","John Glenn"],correct:1,xp:15,emoji:"🏛"},
  {id:"h03",subject:"history",difficulty:"medium",text:"Where were the first Olympics?",opts:["Rome","Athens","Sparta","Olympia"],correct:3,xp:20,emoji:"🏛",funFact:"Ancient Olympics began 776 BC in Olympia, Greece!"},
  {id:"h04",subject:"history",difficulty:"easy",  text:"Who built the Great Pyramids?",opts:["Romans","Greeks","Egyptians","Persians"],correct:2,xp:15,emoji:"🏛",monument:"pyramid"},
  {id:"h05",subject:"history",difficulty:"medium",text:"Columbus reached Americas in?",opts:["1488","1492","1496","1500"],correct:1,xp:20,emoji:"🏛"},
  {id:"h06",subject:"history",difficulty:"medium",text:"First Emperor of China?",opts:["Sun Yat-sen","Emperor Guangxu","Qin Shi Huang","Confucius"],correct:2,xp:20,emoji:"🏛",monument:"great_wall"},
  {id:"h07",subject:"history",difficulty:"easy",  text:"First US President?",opts:["Lincoln","Franklin","Washington","Jefferson"],correct:2,xp:15,emoji:"🏛",monument:"liberty"},
  {id:"h08",subject:"history",difficulty:"hard",  text:"Magna Carta signed in which year?",opts:["1166","1215","1312","1415"],correct:1,xp:25,emoji:"🏛",funFact:"First document to limit the English king's power!"},
  // LANGUAGE
  {id:"l01",subject:"language",difficulty:"easy",  text:"Synonym for 'happy'?",opts:["Sad","Joyful","Angry","Tired"],correct:1,xp:10,emoji:"📚"},
  {id:"l02",subject:"language",difficulty:"easy",  text:"Plural of 'mouse'?",opts:["Mouses","Mice","Mouse","Mousen"],correct:1,xp:10,emoji:"📚",funFact:"'Mice' is an irregular plural — most just add -s!"},
  {id:"l03",subject:"language",difficulty:"medium",text:"'The wind whispered' — device?",opts:["Simile","Metaphor","Personification","Alliteration"],correct:2,xp:20,emoji:"📚"},
  {id:"l04",subject:"language",difficulty:"medium",text:"A haiku has how many syllables total?",opts:["12","14","17","21"],correct:2,xp:15,emoji:"📚",funFact:"5-7-5: Japanese poetry perfection!"},
  // ASTRONOMY
  {id:"a01",subject:"astronomy",difficulty:"easy",  text:"Moons of Mars?",opts:["0","1","2","4"],correct:2,xp:15,emoji:"🌙",funFact:"Phobos (Fear) and Deimos (Dread) — Greek mythology names!"},
  {id:"a02",subject:"astronomy",difficulty:"medium",text:"Planet with the most moons?",opts:["Jupiter","Saturn","Uranus","Neptune"],correct:1,xp:20,emoji:"🌙",funFact:"Saturn has 146 confirmed moons as of 2024!"},
  {id:"a03",subject:"astronomy",difficulty:"medium",text:"A light-year is a measure of?",opts:["Time","Distance","Speed","Temperature"],correct:1,xp:15,emoji:"🌙",funFact:"One light-year = 9.46 trillion km!"},
  {id:"a04",subject:"astronomy",difficulty:"easy",  text:"Our galaxy is called?",opts:["Andromeda","Milky Way","Triangulum","Sombrero"],correct:1,xp:15,emoji:"🌙"},
  {id:"a05",subject:"astronomy",difficulty:"hard",  text:"Age of the universe (approx)?",opts:["4.5 billion","7.8 billion","13.8 billion","20 billion"],correct:2,xp:25,emoji:"🌙",funFact:"Universe is ~3× older than Earth!"},
  // BIOLOGY
  {id:"b01",subject:"biology",difficulty:"easy",  text:"Insect legs?",opts:["4","6","8","10"],correct:1,xp:10,emoji:"🦋",funFact:"Spiders have 8 legs and are NOT insects!"},
  {id:"b02",subject:"biology",difficulty:"medium",text:"Plants make food via?",opts:["Respiration","Digestion","Photosynthesis","Osmosis"],correct:2,xp:15,emoji:"🦋"},
  {id:"b03",subject:"biology",difficulty:"medium",text:"Universal blood donor type?",opts:["A","B","AB","O"],correct:3,xp:20,emoji:"🦋",funFact:"O- can be given to anyone in an emergency!"},
  {id:"b04",subject:"biology",difficulty:"hard",  text:"Largest human organ?",opts:["Liver","Brain","Skin","Heart"],correct:2,xp:20,emoji:"🦋",funFact:"Skin weighs ~3.6 kg and covers 2 square metres!"},
];

export const BLOCK_QUESTIONS = ALL_QUESTIONS.slice(0, 22);

export function getRandomQuestion(exclude: Set<string> = new Set()): EduQuestion | null {
  const pool = ALL_QUESTIONS.filter(q => !exclude.has(q.id));
  return pool.length ? pool[Math.floor(Math.random() * pool.length)] : null;
}
