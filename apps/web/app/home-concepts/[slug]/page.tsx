import type { Metadata } from "next";
import { notFound } from "next/navigation";
import {
  ConceptExperience,
  type ConceptSlug,
} from "../../components/home-concepts/HomeConcepts";

type Props = { params: { slug: string } };

const conceptSlugs: ConceptSlug[] = [
  "aurora-story",
  "learning-worlds",
  "signal-studio",
  "human-journal",
];

const names: Record<ConceptSlug, string> = {
  "aurora-story": "Aurora Story",
  "learning-worlds": "Learning Worlds",
  "signal-studio": "Signal Studio",
  "human-journal": "Human Journal",
};

export function generateStaticParams() {
  return conceptSlugs.map((slug) => ({ slug }));
}

export function generateMetadata({ params }: Props): Metadata {
  const slug = params.slug as ConceptSlug;
  return {
    title: `${names[slug] ?? "Homepage concept"} — Salareen`,
    description: "Interactive Salareen homepage design concept.",
  };
}

export default function HomeConceptPage({ params }: Props) {
  if (!conceptSlugs.includes(params.slug as ConceptSlug)) notFound();
  return <ConceptExperience slug={params.slug as ConceptSlug} />;
}
