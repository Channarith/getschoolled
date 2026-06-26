export type TabId = "home" | "drive" | "mylist" | "careers" | "notifications" | "settings";

export type NavigateTo =
  | { tab: "drive"; courseId: string }
  | { tab: TabId };
