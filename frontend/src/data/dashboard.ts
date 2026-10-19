/**
 * UI-1: Presentation-only sample data. All quantities, OVRs, fixtures, and club
 * stories in this file are fictional mockup values; NONE come from Python.
 * Future UI-2: a typed read model returned by Python replaces this module.
 */
export interface TableRow {
  clubId: string;
  name: string;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  goalDifference: number;
  points: number;
  accent: string;
}

export interface Competition {
  id: string;
  title: string;
  kind: "league" | "cup";
  table?: TableRow[];
  cupProgress?: { stage: string; description: string; nextTie: string };
}

export interface LineupPlayer {
  id: string;
  name: string;
  position: string;
  overall: number;
  x: number;
  y: number;
  skin: string;
  hair: string;
}

export interface Notification {
  id: string;
  category: "player" | "medical" | "team" | "scouting" | "board";
  title: string;
  preview: string;
  time: string;
  unread: boolean;
  details: string;
}

export interface ClubStory {
  id: string;
  category: string;
  title: string;
  preview: string;
  time: string;
  type: "stadium" | "star" | "trophy" | "tactics";
}

const premierTable: TableRow[] = [
  { clubId: "highfield", name: "Highfield City", played: 34, won: 24, drawn: 6, lost: 4, goalDifference: 42, points: 78, accent: "#386cd7" },
  { clubId: "northbridge", name: "Northbridge FC", played: 34, won: 22, drawn: 7, lost: 5, goalDifference: 32, points: 73, accent: "#f5f7fa" },
  { clubId: "oakmere", name: "Oakmere Athletic", played: 34, won: 20, drawn: 8, lost: 6, goalDifference: 26, points: 68, accent: "#e44762" },
  { clubId: "westborough", name: "Westborough United", played: 34, won: 19, drawn: 7, lost: 8, goalDifference: 20, points: 64, accent: "#41b766" },
  { clubId: "greenwich", name: "Greenwich Rovers", played: 34, won: 18, drawn: 8, lost: 8, goalDifference: 18, points: 62, accent: "#fab847" },
  { clubId: "stonebridge", name: "Stonebridge Town", played: 34, won: 18, drawn: 8, lost: 8, goalDifference: 14, points: 60, accent: "#587cc4" },
  { clubId: "harbour", name: "Harbour Town", played: 34, won: 11, drawn: 8, lost: 15, goalDifference: -6, points: 41, accent: "#639ce4" },
  { clubId: "redhaven", name: "Redhaven FC", played: 34, won: 11, drawn: 8, lost: 15, goalDifference: -8, points: 41, accent: "#ec3955" },
  { clubId: "eastgate", name: "Eastgate FC", played: 34, won: 9, drawn: 12, lost: 13, goalDifference: -11, points: 39, accent: "#f35b77" },
];

const championsTable: TableRow[] = [
  { clubId: "northbridge", name: "Northbridge FC", played: 8, won: 5, drawn: 1, lost: 2, goalDifference: 10, points: 16, accent: "#f5f7fa" },
  { clubId: "atlas", name: "Atlas Sporting", played: 8, won: 5, drawn: 1, lost: 2, goalDifference: 9, points: 16, accent: "#5f88fc" },
  { clubId: "royal", name: "Royal Port", played: 8, won: 4, drawn: 3, lost: 1, goalDifference: 8, points: 15, accent: "#e9c15e" },
  { clubId: "valencia", name: "Valencia Blue", played: 8, won: 4, drawn: 2, lost: 2, goalDifference: 5, points: 14, accent: "#42d6ba" },
  { clubId: "milan", name: "Milan East", played: 8, won: 4, drawn: 1, lost: 3, goalDifference: 4, points: 13, accent: "#e94965" },
  { clubId: "porto", name: "Porto North", played: 8, won: 4, drawn: 1, lost: 3, goalDifference: 3, points: 13, accent: "#82b6ed" },
];

export const competitions: Competition[] = [
  { id: "premier", title: "Premier League", kind: "league", table: premierTable },
  { id: "champions", title: "Champions League", kind: "league", table: championsTable },
  { id: "fa-cup", title: "FA Cup", kind: "cup", cupProgress: { stage: "Semi-final", description: "Cup draw and qualification history will come from the Python competition runner.", nextTie: "Northbridge FC vs Kingsport FC" } },
  { id: "carabao", title: "Carabao Cup", kind: "cup", cupProgress: { stage: "Eliminated – Round 4", description: "An example knockout status, not a real match result.", nextTie: "No upcoming ties" } },
];

export const lineupPlayers: LineupPlayer[] = [
  { id: "lw", name: "Murphy", position: "LW", overall: 79, x: 17, y: 15, skin: "#ce9b77", hair: "#33251d" },
  { id: "st", name: "Taylor", position: "ST", overall: 84, x: 50, y: 10, skin: "#e5b18c", hair: "#352d27" },
  { id: "rw", name: "Santos", position: "RW", overall: 78, x: 83, y: 15, skin: "#b97752", hair: "#211916" },
  { id: "lcm", name: "Foster", position: "CM", overall: 76, x: 25, y: 40, skin: "#ecc5a6", hair: "#3c2b21" },
  { id: "cam", name: "Evans", position: "CAM", overall: 82, x: 50, y: 35, skin: "#deb395", hair: "#221c1a" },
  { id: "rcm", name: "Bennett", position: "CM", overall: 77, x: 75, y: 40, skin: "#b98567", hair: "#241f21" },
  { id: "lb", name: "Williams", position: "LB", overall: 75, x: 12, y: 67, skin: "#be7958", hair: "#202020" },
  { id: "lcb", name: "Clark", position: "CB", overall: 79, x: 37, y: 66, skin: "#956447", hair: "#272120" },
  { id: "rcb", name: "Nguyen", position: "CB", overall: 80, x: 63, y: 66, skin: "#d8a07d", hair: "#30221d" },
  { id: "rb", name: "Peters", position: "RB", overall: 76, x: 88, y: 67, skin: "#e3b89f", hair: "#48372a" },
  { id: "gk", name: "Hughes", position: "GK", overall: 81, x: 50, y: 88, skin: "#e3b797", hair: "#30251e" },
];

export const notifications: Notification[] = [
  { id: "player", category: "player", title: "Player Feedback", preview: "Lewis Hart is pleased with your handling of his recent role.", time: "2 days ago", unread: true, details: "Lewis Hart has expressed his satisfaction with recent first-team opportunities and training feedback." },
  { id: "medical", category: "medical", title: "Injury Update", preview: "Nathan Cole has picked up a minor knock in training.", time: "3 days ago", unread: true, details: "The medical staff report a minor knock. This is illustrative content; injuries are not yet wired to the game world." },
  { id: "team", category: "team", title: "Squad Dynamics", preview: "Several players are in good form and morale is high.", time: "4 days ago", unread: false, details: "The assistant manager is encouraged by the atmosphere around the dressing room." },
  { id: "scouting", category: "scouting", title: "Scouting Report", preview: "A new opponent report is available for review.", time: "4 days ago", unread: false, details: "Example report: examine the next opponent's tactical tendencies before kickoff." },
  { id: "board", category: "board", title: "Board Update", preview: "The board are pleased with the team's recent results.", time: "6 days ago", unread: false, details: "The board appreciates the team's current league position. Club board systems will arrive in a future phase." },
];

export const stories: ClubStory[] = [
  { id: "title", type: "trophy", category: "Club News", title: "Northbridge close in on promotion glory", preview: "A pivotal stretch of the season awaits Northbridge as the race heats up.", time: "1 day ago" },
  { id: "stadium", type: "stadium", category: "Club Update", title: "A special night at Northbridge Stadium", preview: "The fans are preparing for a crucial home fixture.", time: "3 days ago" },
  { id: "form", type: "star", category: "Player News", title: "Young star shines in crucial win", preview: "One of the club's prospects continues to attract attention.", time: "4 days ago" },
  { id: "prep", type: "tactics", category: "Match Preview", title: "Coaching staff prepare for Redhaven", preview: "Training focus shifts to the upcoming league match.", time: "5 days ago" },
];

export const demoDashboard = {
  club: {
    name: "Northbridge FC",
    manager: "Alex Manager",
    league: "Premier League",
    position: "2nd",
    points: 73,
    season: "2026/27",
    stadium: "Northbridge Stadium",
    capacity: "38,421",
    clubStatus: "Professional",
    objective: "Challenge for the title",
    recentResults: ["W", "W", "D", "W", "L"] as const,
  },
  nextMatch: { opponent: "Redhaven FC", competition: "Premier League", isoDate: "2027-05-08", kickoff: "15:00", stadium: "Northbridge Stadium", isHome: true },
  teamMetrics: [
    { key: "morale", label: "Morale", score: 91, word: "Very good", icon: "smile" as const, color: "mint" },
    { key: "condition", label: "Condition", score: 78, word: "Good", icon: "heart" as const, color: "mint" },
    { key: "chemistry", label: "Chemistry", score: 77, word: "Strong", icon: "users" as const, color: "blue" },
    { key: "form", label: "Form", score: 76, word: "Good", icon: "trending" as const, color: "mint" },
  ],
  formation: "4-3-3",
  mentality: "Attacking",
  lineupPlayers,
  notifications,
  stories,
};
