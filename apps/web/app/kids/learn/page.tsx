"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { KIDS_LESSONS } from "../../lib/kidsLearning";

function KidsLessonPlayer() {
  const params = useSearchParams();
  const lesson = KIDS_LESSONS[params.get("course") ?? ""] ?? KIDS_LESSONS["kids-abc-adventures"];
  const [sceneIndex, setSceneIndex] = useState(0);
  const [selected, setSelected] = useState("");
  const [celebrating, setCelebrating] = useState(false);
  const scene = lesson.scenes[sceneIndex];
  const correct = selected === scene.answer;

  useEffect(() => {
    setSceneIndex(0);
    setSelected("");
  }, [lesson.id]);

  const celebrateTimer = useRef<number | null>(null);
  useEffect(() => () => {
    if (celebrateTimer.current !== null) window.clearTimeout(celebrateTimer.current);
  }, []);

  function choose(choice: string) {
    setSelected(choice);
    if (choice === scene.answer) {
      setCelebrating(true);
      if (celebrateTimer.current !== null) window.clearTimeout(celebrateTimer.current);
      celebrateTimer.current = window.setTimeout(() => setCelebrating(false), 900);
    }
  }

  function next() {
    setSelected("");
    setSceneIndex((current) => Math.min(current + 1, lesson.scenes.length - 1));
  }

  function speak() {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(
      new SpeechSynthesisUtterance(`${scene.title}. ${scene.instruction}. ${scene.question}`),
    );
  }

  const finished = correct && sceneIndex === lesson.scenes.length - 1;

  return (
    <main className="kids-lesson" style={{ "--lesson-color": lesson.color } as React.CSSProperties}>
      <nav className="kids-lesson-nav">
        <Link href="/kids">← All Kids Courses</Link>
        <span>{sceneIndex + 1} of {lesson.scenes.length}</span>
      </nav>

      <header className="kids-lesson-header">
        <span className="kids-lesson-mascot" aria-hidden>{lesson.emoji}</span>
        <div>
          <p>PICTURE LEARNING ADVENTURE</p>
          <h1>{lesson.title}</h1>
        </div>
      </header>

      <div className="kids-progress" aria-label={`Lesson ${sceneIndex + 1} of ${lesson.scenes.length}`}>
        {lesson.scenes.map((_, index) => (
          <span key={index} className={index <= sceneIndex ? "done" : ""} />
        ))}
      </div>

      <section className={`kids-scene ${celebrating ? "celebrate" : ""}`}>
        <button className="kids-listen" onClick={speak} aria-label="Read this activity aloud">
          🔊 Read aloud
        </button>
        <h2>{scene.title}</h2>
        <p className="kids-instruction">{scene.instruction}</p>

        <div className="kids-picture-stage" aria-label={scene.labels?.join(", ")}>
          {scene.pictures.map((picture, index) => (
            <figure key={`${picture}-${index}`} style={{ animationDelay: `${index * 120}ms` }}>
              <span aria-hidden>{picture}</span>
              {scene.labels?.[index] && <figcaption>{scene.labels[index]}</figcaption>}
            </figure>
          ))}
        </div>

        <div className="kids-question">
          <h3>{scene.question}</h3>
          <div className="kids-choices">
            {scene.choices.map((choice) => {
              const state = selected === choice
                ? choice === scene.answer ? "correct" : "wrong"
                : "";
              return (
                <button key={choice} className={state} onClick={() => choose(choice)}>
                  {choice}
                </button>
              );
            })}
          </div>
          {selected && (
            <p className={`kids-feedback ${correct ? "correct" : "wrong"}`} role="status">
              {correct ? "🌟 Great job! You got it!" : "💛 Nice try! Look at the pictures and try again."}
            </p>
          )}
        </div>

        {correct && !finished && (
          <button className="kids-next" onClick={next}>Next picture →</button>
        )}
        {finished && (
          <div className="kids-finished">
            <div aria-hidden>🎉 ⭐ 🎈 ⭐ 🎉</div>
            <h2>Adventure complete!</h2>
            <p>You learned with every picture.</p>
            <Link href="/kids">Choose another adventure</Link>
          </div>
        )}
      </section>
    </main>
  );
}

export default function KidsLearnPage() {
  return (
    <Suspense fallback={<main className="kids-lesson"><p>Loading your picture adventure…</p></main>}>
      <KidsLessonPlayer />
    </Suspense>
  );
}
