export type TabId = "home" | "drive" | "mylist" | "notifications" | "settings";

export type NavigateTo =
  | { tab: "drive"; courseId: string }
  | { tab: TabId };
