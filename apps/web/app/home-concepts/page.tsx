import type { Metadata } from "next";
import { ConceptGallery } from "../components/home-concepts/HomeConcepts";

export const metadata: Metadata = {
  title: "Homepage concept review — Salareen",
  description: "Four interactive directions for the next Salareen homepage.",
};

export default function HomeConceptsPage() {
  return <ConceptGallery />;
}
