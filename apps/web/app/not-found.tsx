import FriendlyError from "./components/FriendlyError";

export const metadata = { title: "Sala can't find that page - Salareen", robots: { index: false } };

export default function NotFound() {
  return <FriendlyError status={404} kind="notfound" />;
}
