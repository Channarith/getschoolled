"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import BiometricSetupAssistant from "../components/BiometricSetupAssistant";
import MascotDraggable from "../components/MascotDraggable";
import { type MascotScene, sceneForMode } from "../lib/mascotPose";
import { AGE_MAX, AGE_MIN, AGE_OPTIONS, clampAge } from "../lib/learnerCheck";
import AccountStep from "./AccountStep";
import { useT } from "../lib/i18n";
import {
  AUTH_EVENT,
  completeOnboarding,
  getConsumerPlans,
  getFreePlanOffer,
  getMe,
  recordConsent,
  startBillingCheckout,
  getOnboardingStatus,
  getToken,
  listStudents,
  selectOnboardingPlan,
  skipLearningProfile,
  submitLearningProfile,
  submitOnboardingBilling,
  submitOnboardingLearner,
  submitOnboardingSurveyAnalytics,
  type ConsumerPlan,
} from "../lib/api";
import { formatMonthlyPrice, orderedConsumerPlans } from "../lib/consumerPlansDisplay";
import styles from "./Onboarding.module.css";

// The learn step now shows exactly one mode card per page across every
// viewport (see apps/web/app/lib/layoutWidth.ts). That keeps the MascotActor
// in the left art pane at its full stage size so it visibly acts out the
// focused mode on both phones and desktops.
const LEARN_MODES_PER_PAGE = 1 as const;

const MODES = [
  { id: "video", art: "mode-video", label: "Watching videos", blurb: "Short lessons you can pause and replay." },
  { id: "live_teacher", art: "mode-person", label: "A live teacher", blurb: "Learning in person or in a live class." },
  { id: "presentation", art: "mode-presentation", label: "Presentations", blurb: "Slides and visual walkthroughs." },
  { id: "reading", art: "mode-reading", label: "Reading a book", blurb: "Taking your time with text and notes." },
  { id: "tutoring", art: "mode-tutoring", label: "1:1 tutoring", blurb: "One coach, just for you." },
  { id: "gaming", art: "mode-gaming", label: "Gaming", blurb: "Learning by playing and doing." },
] as const;
type ModeId = (typeof MODES)[number]["id"];

type Step = "account" | "about" | "learn" | "consent" | "identity" | "plan" | "payment";
// Consent is now a required onboarding step that sits BETWEEN "learn" and
// "identity". Users asked us to remove the standalone /consent link from the
// footer so people don't have to hunt it down later — ticking the checklist
// once at sign-up is the canonical path. All items default UNCHECKED so the
// user has to make a deliberate choice; "Continue" is enabled with zero items
// ticked because every scope is OPTIONAL (biometrics/vision use an opt-in,
// name-only fallback). The acknowledgement checkbox at the bottom is the only
// required field — it records that the user saw the notice.
const BASE_STEPS: Step[] = ["about", "learn", "consent", "identity", "plan"];
const STEP_LABEL: Record<Step, string> = {
  account: "Your account",
  about: "About you",
  learn: "How you learn",
  consent: "Privacy & consent",
  identity: "Learner Check",
  plan: "Your plan",
  payment: "Your plan",
};
const STORAGE = {
  step: "setup_assistant_step",
  name: "onboarding_learner_name",
  age: "onboarding_age",
  ageBand: "onboarding_age_band",
  ratings: "onboarding_modality_ratings",
  student: "onboarding_student_id",
  owner: "onboarding_account_id",
  plan: "onboarding_plan",
  consent: "onboarding_consent",
};

// Each entry is one toggle on the consent step. The `scope` string matches
// the identity service's /consent endpoint vocabulary (face_recognition,
// attention_tracking, recording, cross_class_memory) so persistence is a
// straight pass-through to recordConsent({scope, granted}).
const CONSENT_SCOPES: Array<{ scope: string; label: string; description: string }> = [
  {
    scope: "face_recognition",
    label: "Face recognition",
    description:
      "Let Salareen recognize me across classes using self-hosted vision models (never leaves the configured boundary).",
  },
  {
    scope: "attention_tracking",
    label: "Attention / engagement tracking",
    description:
      "Use anonymous engagement signals to pace lessons and nudge me when I lose focus.",
  },
  {
    scope: "recording",
    label: "Session recording",
    description: "Record live classes I attend so I can review them later.",
  },
  {
    scope: "cross_class_memory",
    label: "Cross-class memory",
    description: "Remember progress across classes so my next lesson picks up where I left off.",
  },
];

function ageBandFor(age: number) {
  if (age < 13) return "child";
  if (age < 18) return "teen";
  return "adult";
}

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export default function OnboardingPage() {
  const { t } = useT();
  const router = useRouter();
  const [step, setStep] = useState<Step>("about");
  const [includeAccount, setIncludeAccount] = useState(false);
  const [name, setName] = useState("");
  const [age, setAge] = useState<number | "">("");
  const ageRef = useRef<HTMLSelectElement>(null);
  const [ratings, setRatings] = useState<Partial<Record<ModeId, number>>>({});
  const [focus, setFocus] = useState<ModeId>("video");
  const [modePage, setModePage] = useState(0);
  const perPage = LEARN_MODES_PER_PAGE;
  const advanceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [studentId, setStudentId] = useState("");
  const [consentGrants, setConsentGrants] = useState<Record<string, boolean>>({});
  const [consentAck, setConsentAck] = useState(false);
  const [plan, setPlan] = useState("free");
  const [freeOffer, setFreeOffer] = useState(true);
  const [consumerPlans, setConsumerPlans] = useState<ConsumerPlan[]>([]);
  const [billing, setBilling] = useState({
    line1: "", line2: "", city: "", state: "", postal_code: "", country: "US",
    card_number: "", exp_month: 12, exp_year: new Date().getFullYear() + 2, cvv: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // Guards against double-clicks before React commits the disabled state.
  const busyRef = useRef(false);

  useEffect(() => {
    if (!getToken()) {
      setIncludeAccount(true);
      setStep("account");
      return;
    }
    getOnboardingStatus().then((s) => {
      if (s.completed) router.replace("/");
    }).catch(() => {});
    const saved = localStorage.getItem(STORAGE.step) as Step | null;
    const savedStudent = localStorage.getItem(STORAGE.student) || "";
    const known = (["account", ...BASE_STEPS] as Step[]).includes(saved as Step);
    const resumable = Boolean(saved && known && saved !== "account" && (saved === "about" || savedStudent));
    const savedName = localStorage.getItem(STORAGE.name) || "";
    setName(savedName);
    const savedAge = Number(localStorage.getItem(STORAGE.age));
    if (savedAge) setAge(savedAge);
    setRatings(readJson(STORAGE.ratings, {}));
    // Saved steps and the learner id are only resumed for the account that
    // made them. A leftover id from another signup skipped the survey and sent
    // the face check to a learner this account does not own (404).
    void (async () => {
      const me = await getMe().catch(() => null);
      if (!me) {
        setStudentId(savedStudent);
        if (resumable) setStep(saved as Step);
        return;
      }
      if (!savedName && me.display_name) setName((current) => current || me.display_name);
      const owner = localStorage.getItem(STORAGE.owner);
      const owned = savedStudent
        ? await listStudents()
          .then((r) => r.students.some((s) => s.id === savedStudent))
          .catch(() => true)
        : true;
      if ((owner && owner !== me.id) || !owned) {
        Object.values(STORAGE).forEach((key) => localStorage.removeItem(key));
        localStorage.setItem(STORAGE.owner, me.id);
        setRatings({});
        setAge("");
        setName(me.display_name || "");
        setStudentId("");
        setStep("about");
        return;
      }
      localStorage.setItem(STORAGE.owner, me.id);
      setStudentId(savedStudent);
      if (resumable) setStep(saved as Step);
    })();
    setPlan(localStorage.getItem(STORAGE.plan) || "free");
    // Rehydrate consent choices so a page refresh mid-onboarding doesn't lose
    // what the user already ticked. We only read; we don't resurrect the ack
    // automatically — the user still has to confirm the current notice.
    const savedConsent = readJson<{ grants?: Record<string, boolean> } | null>(STORAGE.consent, null);
    if (savedConsent?.grants) setConsentGrants(savedConsent.grants);
    getFreePlanOffer().then((offer) => {
      setFreeOffer(offer.available);
      if (!offer.available) {
        setPlan((current) => (current === "free" ? "basic" : current));
      }
    }).catch(() => undefined);
    getConsumerPlans()
      .then((catalog) => setConsumerPlans(orderedConsumerPlans(catalog)))
      .catch(() => undefined);
  }, [router]);

  useEffect(() => {
    const onAuthChange = () => {
      if (!getToken() && step !== "account") {
        Object.values(STORAGE).forEach((key) => localStorage.removeItem(key));
        setIncludeAccount(true);
        setStep("account");
      }
    };
    window.addEventListener(AUTH_EVENT, onAuthChange);
    return () => window.removeEventListener(AUTH_EVENT, onAuthChange);
  }, [step]);

  useEffect(() => {
    localStorage.setItem(STORAGE.step, step === "payment" ? "plan" : step);
  }, [step]);

  useEffect(() => {
    localStorage.setItem(STORAGE.ratings, JSON.stringify(ratings));
  }, [ratings]);

  useEffect(() => {
    localStorage.setItem(STORAGE.plan, plan);
  }, [plan]);

  useEffect(() => {
    setModePage((page) => Math.min(page, Math.ceil(MODES.length / perPage) - 1));
  }, [perPage]);

  // Keep the MascotActor scene in sync with whichever mode card is visible.
  // With one card per page the current page uniquely identifies the mode,
  // so navigating with the pager arrows or dots makes the mascot act out
  // that mode even before the user hovers or focuses the card.
  useEffect(() => {
    if (step !== "learn") return;
    const index = Math.min(Math.max(modePage, 0), MODES.length - 1);
    const mode = MODES[index];
    if (mode) setFocus(mode.id);
  }, [modePage, step]);

  useEffect(() => () => {
    if (advanceRef.current) clearTimeout(advanceRef.current);
  }, []);

  async function run(task: () => Promise<void>) {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setError("");
    try {
      await task();
    } catch (reason) {
      setError(String(reason).replace(/^Error:\s*/, ""));
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  // Desktop mouse wheel / trackpad scroll over the age picker steps the age,
  // like a wheel. Needs a non-passive listener to stop the page scrolling.
  useEffect(() => {
    const select = ageRef.current;
    if (!select) return;
    const onWheel = (event: WheelEvent) => {
      if (Math.abs(event.deltaY) < 1) return;
      event.preventDefault();
      setAge((current) => clampAge((typeof current === "number" ? current : 12) + (event.deltaY > 0 ? 1 : -1)));
    };
    select.addEventListener("wheel", onWheel, { passive: false });
    return () => select.removeEventListener("wheel", onWheel);
  }, [step]);

  const ageValue = typeof age === "number" ? age : 0;
  const aboutReady = name.trim().length > 0 && ageValue >= AGE_MIN && ageValue <= AGE_MAX;
  const ageBand = ageValue ? ageBandFor(ageValue) : "adult";

  function saveAbout() {
    return run(async () => {
      const result = await submitOnboardingLearner({ learner_name: name.trim(), age: ageValue });
      localStorage.setItem(STORAGE.name, name.trim());
      localStorage.setItem(STORAGE.age, String(ageValue));
      localStorage.setItem(STORAGE.ageBand, result.age_band);
      localStorage.setItem(STORAGE.student, result.student.id);
      setStudentId(result.student.id);
      void getMe().then((me) => localStorage.setItem(STORAGE.owner, me.id)).catch(() => undefined);
      setStep("learn");
    });
  }

  const rated = MODES.filter((mode) => ratings[mode.id] != null).length;
  const top = [...MODES].sort((a, b) => (ratings[b.id] ?? 0) - (ratings[a.id] ?? 0))[0];
  const pageCount = Math.ceil(MODES.length / perPage);
  const currentPage = Math.min(modePage, pageCount - 1);
  const pageModes = MODES.slice(currentPage * perPage, currentPage * perPage + perPage);

  function rate(mode: ModeId, value: number) {
    const next = { ...ratings, [mode]: value };
    setRatings(next);
    setFocus(mode);
    if (advanceRef.current) clearTimeout(advanceRef.current);
    const pageDone = pageModes.every((item) => next[item.id] != null);
    if (pageDone && currentPage < pageCount - 1) {
      advanceRef.current = setTimeout(() => setModePage(currentPage + 1), 450);
    }
  }

  function saveLearning() {
    return run(async () => {
      const answers = { modality_ratings: ratings };
      // The identity service returns 404 "unknown student profile" if the
      // cached studentId no longer resolves (common after a backend wipe
      // or when localStorage.onboarding_student points at a student the
      // identity DB has forgotten about). Self-heal in two stages:
      //   1. Re-post the About step from the cached name/age to mint a
      //      fresh student id, then retry submitLearningProfile.
      //   2. If the retry still fails (upstream flake, derive error,
      //      write race), fall back to skipLearningProfile so the user
      //      is NEVER stranded on this step - the learning profile is
      //      optional and the identity step is the gate that matters.
      let effectiveStudentId = studentId;
      let saveOk = true;
      try {
        await submitLearningProfile(effectiveStudentId, answers);
      } catch (reason) {
        const msg = String(reason);
        const is404 = /\b404\b/.test(msg) || /unknown student profile/i.test(msg);
        if (!is404) {
          // Non-404 failure (500, timeout, offline): best-effort skip so
          // the user can still move forward. We only hard-throw if even
          // the skip fails - because at that point there is nothing we
          // can do but stop and surface the error.
          try {
            await skipLearningProfile(effectiveStudentId);
            saveOk = false;
          } catch {
            throw reason;
          }
        } else {
          if (!name.trim() || !ageValue) {
            // Nothing cached to re-create with - bounce them back to About
            // so they can type their name/age again.
            setStep("about");
            throw new Error("We lost your profile - please re-enter your name and age.");
          }
          const refreshed = await submitOnboardingLearner({
            learner_name: name.trim(),
            age: ageValue,
          });
          localStorage.setItem(STORAGE.student, refreshed.student.id);
          setStudentId(refreshed.student.id);
          effectiveStudentId = refreshed.student.id;
          try {
            await submitLearningProfile(effectiveStudentId, answers);
          } catch (retryReason) {
            // Fresh student id was accepted (above createLearner succeeded)
            // but the profile write still failed. Skip gracefully so the
            // user is not stuck on an optional checkpoint.
            try {
              await skipLearningProfile(effectiveStudentId);
              saveOk = false;
            } catch {
              throw retryReason;
            }
          }
        }
      }
      const me = await getMe().catch(() => null);
      if (me && saveOk) {
        void submitOnboardingSurveyAnalytics({ account_id: me.id, student_id: effectiveStudentId, answers })
          .catch(() => undefined);
      }
      window.dispatchEvent(new CustomEvent("aoep-learning-profile-saved"));
      setStep("consent");
    });
  }

  function skipLearning() {
    return run(async () => {
      // Explicit "Skip for now" escape hatch. If skip fails for any reason
      // we still advance - the learning profile is optional, and the user
      // asked to move on. The identity step requires a valid student id,
      // which is already in state (studentId) or self-heals there.
      try {
        await skipLearningProfile(studentId);
      } catch {
        /* best-effort - the user chose to skip */
      }
      setStep("consent");
    });
  }

  function saveConsent() {
    // Persist each scope independently through the identity service's /consent
    // endpoint (same endpoint the old standalone /consent page used — reused,
    // not forked, so audit history is unchanged). We write all four scopes
    // every time: a false value is a positive "I decided to leave this off"
    // record, which is what regulators want to see. If any scope write fails
    // we still advance to identity — the acknowledgement itself is persisted
    // locally so the user is not forced to re-tick on refresh. The identity
    // step depends on these grants but has its own age-gated biometric-consent
    // flow for guardians, so a transient write failure can't strand onboarding.
    return run(async () => {
      if (!consentAck) {
        throw new Error("Please acknowledge the privacy notice to continue.");
      }
      const writes = CONSENT_SCOPES.map((s) =>
        recordConsent({ scope: s.scope, granted: Boolean(consentGrants[s.scope]) }).catch(
          () => null,
        ),
      );
      await Promise.all(writes);
      try {
        localStorage.setItem(
          STORAGE.consent,
          JSON.stringify({ ack: true, grants: consentGrants, at: Date.now() }),
        );
      } catch {
        /* best-effort */
      }
      setStep("identity");
    });
  }

  function savePlan() {
    if (plan !== "free") {
      setStep("payment");
      return;
    }
    return run(async () => {
      await selectOnboardingPlan(plan);
      await finish();
    });
  }

  function savePayment() {
    return run(async () => {
      const me = await getMe();
      const tier = plan === "vip" ? "premium" : plan;
      const session = await startBillingCheckout(me.id, tier);
      if (session.url && /^https?:\/\//i.test(session.url)) {
        window.location.href = session.url;
        return;
      }
      const sandbox = session.provider === "sandbox" || (session.url || "").startsWith("sandbox://");
      if (!sandbox) {
        throw new Error(session.instructions || "Checkout is not available for this plan yet.");
      }
      await submitOnboardingBilling({
        line1: billing.line1,
        line2: billing.line2,
        city: billing.city,
        state: billing.state,
        postal_code: billing.postal_code,
        country: billing.country || "US",
        card_number: billing.card_number,
        exp_month: Number(billing.exp_month),
        exp_year: Number(billing.exp_year),
        cvv: billing.cvv,
      });
      await selectOnboardingPlan(tier);
      await finish();
    });
  }

  async function finish() {
    await completeOnboarding({ learner_name: name.trim(), age_band: ageBand });
    Object.values(STORAGE).forEach((key) => localStorage.removeItem(key));
    localStorage.removeItem("onboarding_step");
    router.push("/");
  }

  const stepOrder: Step[] = includeAccount ? ["account", ...BASE_STEPS] : BASE_STEPS;
  const stepIndex = Math.max(0, stepOrder.indexOf(step === "payment" ? "plan" : step));
  const stepLabel = `Step ${stepIndex + 1} of ${stepOrder.length} · ${STEP_LABEL[step]}`;

  // Scene the MascotActor plays in the art pane. Recomputed per step so the
  // mascot flies in on sign-in, morphs by age on "About you", acts out the
  // focused learning mode, and idles on plan/payment.
  const mascotScene: MascotScene = useMemo(() => {
    if (step === "account") return { kind: "flyin-point", pointAt: "down" };
    if (step === "about") return { kind: "age-morph", age: typeof age === "number" ? age : 30 };
    if (step === "learn") return sceneForMode(focus);
    if (step === "consent") return { kind: "idle" };
    if (step === "plan") return { kind: "dance" };
    return { kind: "idle" };
  }, [step, age, focus]);

  if (step === "identity" && studentId) {
    return (
      <BiometricSetupAssistant
        studentId={studentId}
        ageBand={ageBand}
        stepLabel={stepLabel}
        onBack={() => setStep("consent")}
        onComplete={() => setStep("plan")}
        onSkip={() => setStep("plan")}
      />
    );
  }

  return (
    <main className={`${styles.shell} aoep-immersive-setup aoep-viewport-shell`} data-step={step}>
      <header className={styles.topbar}>
        <span className={styles.brand}>Salareen</span>
        <div className={styles.progress} aria-label={stepLabel}>
          {stepOrder.map((item, index) => (
            <span key={item} className={index <= stepIndex ? styles.progressOn : ""} />
          ))}
        </div>
        <span className={styles.stepLabel}>{stepLabel}</span>
      </header>
      <div className={styles.split}>
        <div className={styles.artPane} data-mascot-stage>
          <MascotDraggable scene={mascotScene} />
        </div>
        <div className={styles.pane}>

      {step === "account" && (
        <AccountStep onDone={() => { setIncludeAccount(true); setStep("about"); }} />
      )}

      {step === "about" && (
        <section className={styles.panel}>
          <span className={styles.eyebrow}>About you</span>
          <h1>What should we call you?</h1>
          <p className={styles.lede}>This name appears on your profile and in class. About two minutes to finish setup.</p>
          <label className={styles.field}>
            <span>Profile name</span>
            <div className={styles.nameRow} data-mascot-target="about-name">
              <input
                autoFocus
                name="name"
                autoComplete="nickname"
                value={name}
                placeholder="e.g. Maya"
                maxLength={80}
                aria-describedby="profile-name-help"
                onChange={(event) => setName(event.target.value)}
                onKeyDown={(event) => { if (event.key === "Enter" && aboutReady) void saveAbout(); }}
              />
            </div>
            <small id="profile-name-help" className={styles.help}>
              The name on your profile. A nickname is fine. It doesn’t need to be your legal name.
            </small>
          </label>
          <div className={styles.field}>
            <span id="age-label">How old are you?</span>
            <div className={styles.ageRow} data-mascot-target="about-age">
              <div className={styles.ageWheel}>
                <select
                  ref={ageRef}
                  name="age"
                  aria-labelledby="age-label"
                  value={age === "" ? "" : String(age)}
                  onChange={(event) => setAge(event.target.value ? Number(event.target.value) : "")}
                >
                  <option value="" disabled>Choose</option>
                  {AGE_OPTIONS.map((value) => (
                    <option key={value} value={value}>{value}</option>
                  ))}
                </select>
                <span aria-hidden="true">years</span>
              </div>
              {ageValue > 0 && (
                <span className={styles.band}>
                  {ageBand === "child" ? "Kids experience" : ageBand === "teen" ? "Teen experience" : "Adult experience"}
                </span>
              )}
            </div>
            {ageValue > 0 && ageBand !== "adult" && (
              <p className={styles.note}>A parent or guardian will be asked to approve camera and voice setup.</p>
            )}
          </div>
          {error && <p className={styles.error} role="alert">{error}</p>}
          <div className={styles.actions}>
            <button
              className={styles.primary}
              disabled={busy || !aboutReady}
              onClick={() => void saveAbout()}
              data-mascot-target="about-continue"
            >
              {busy ? "Saving…" : "Continue"}
            </button>
          </div>
        </section>
      )}

      {step === "learn" && (
        <section className={`${styles.panel} ${styles.panelWide}`}>
          <span className={styles.eyebrow}>{name ? `Nice to meet you, ${name}` : "How you learn"}</span>
          <h1>How do you learn best?</h1>
          <p className={styles.lede}>
            Rate each from 1 (not for me) to 10 (I love it).
            {rated === MODES.length && top && <> Favorite so far: <b>{top.label.toLowerCase()}</b>.</>}
          </p>
          <div className={styles.modes} data-per-page={perPage}>
            {pageModes.map((mode) => {
              const value = ratings[mode.id];
              return (
                <article
                  key={mode.id}
                  className={`${styles.mode} ${focus === mode.id ? styles.modeFocus : ""}`}
                  onMouseEnter={() => setFocus(mode.id)}
                  onFocus={() => setFocus(mode.id)}
                  data-mascot-target={focus === mode.id ? "learn-card" : undefined}
                >
                  <div className={styles.modeArt}>
                    <Image src={`/setup-assistant/${mode.art}.webp`} alt="" fill priority sizes="(max-width: 839px) 100vw, 50vw" />
                  </div>
                  {value != null && <span className={styles.modeScore}>{value}</span>}
                  <div className={styles.modeBody}>
                    <h3>{mode.label}</h3>
                    <p>{mode.blurb}</p>
                    <div
                      className={styles.scale}
                      role="radiogroup"
                      aria-label={`Rate ${mode.label} from 1 to 10`}
                      onKeyDown={(event) => {
                        const delta = event.key === "ArrowRight" || event.key === "ArrowUp" ? 1
                          : event.key === "ArrowLeft" || event.key === "ArrowDown" ? -1 : 0;
                        if (!delta) return;
                        event.preventDefault();
                        rate(mode.id, Math.min(10, Math.max(1, (value ?? 5) + delta)));
                      }}
                    >
                      {Array.from({ length: 10 }, (_, index) => index + 1).map((n) => (
                        <button
                          key={n}
                          type="button"
                          role="radio"
                          aria-checked={value === n}
                          aria-label={`${n}`}
                          tabIndex={(value ?? 1) === n ? 0 : -1}
                          className={`${value != null && n <= value ? styles.scaleOn : ""} ${value === n ? styles.scalePick : ""}`}
                          onClick={() => rate(mode.id, n)}
                        >{n}</button>
                      ))}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
          <div className={styles.pager}>
            <button
              type="button"
              className={styles.pagerArrow}
              aria-label="Previous"
              disabled={currentPage === 0}
              onClick={() => setModePage(currentPage - 1)}
            >‹</button>
            {Array.from({ length: pageCount }, (_, index) => {
              const done = MODES.slice(index * perPage, index * perPage + perPage).every((item) => ratings[item.id] != null);
              return (
                <button
                  key={index}
                  type="button"
                  aria-label={`Page ${index + 1} of ${pageCount}`}
                  aria-current={index === currentPage ? "step" : undefined}
                  className={`${styles.pagerDot} ${index === currentPage ? styles.pagerDotOn : ""} ${done ? styles.pagerDotDone : ""}`}
                  onClick={() => setModePage(index)}
                />
              );
            })}
            <button
              type="button"
              className={styles.pagerArrow}
              aria-label="Next"
              disabled={currentPage >= pageCount - 1}
              onClick={() => setModePage(currentPage + 1)}
            >›</button>
          </div>
          {error && <p className={styles.error} role="alert">{error}</p>}
          <div className={styles.actions}>
            <button
              className={styles.primary}
              disabled={busy || rated < MODES.length}
              onClick={() => void saveLearning()}
              /* Second waypoint for the overlay mascot's `learn` tour.
                 The mascot walks from the active rating card to this
                 Continue button once all modes are rated, so the user
                 sees exactly where to click next. STEP_TOURS.learn is
                 ["learn-card", "learn-continue"]. */
              data-mascot-target="learn-continue"
            >
              {busy ? "Saving…" : rated < MODES.length ? `Rate ${MODES.length - rated} more` : "Continue"}
            </button>
            <button
              className={styles.ghost}
              disabled={busy}
              onClick={() => void skipLearning()}
              title="Skip the learning survey - this step is optional"
            >
              Skip for now
            </button>
            <button className={styles.ghost} onClick={() => setStep("about")}>Back</button>
          </div>
        </section>
      )}

      {step === "consent" && (
        <section className={styles.panel}>
          <span className={styles.eyebrow}>Privacy & consent</span>
          <h1>Choose what Sala can use.</h1>
          <p className={styles.lede}>
            Every item below is <strong>optional</strong>. Salareen works without any of them —
            each unlocks a feature. Vision/biometric data is processed by self-hosted models and
            never leaves the configured boundary. You can change any choice later under{" "}
            <a href="/account">Account → Privacy</a>.
          </p>
          <div style={{ display: "grid", gap: 10, margin: "8px 0 14px" }}>
            {CONSENT_SCOPES.map((s) => {
              const on = Boolean(consentGrants[s.scope]);
              return (
                <label
                  key={s.scope}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "22px 1fr",
                    gap: 10,
                    padding: 12,
                    borderRadius: 10,
                    border: on ? "1px solid rgba(110,168,254,0.55)" : "1px solid var(--border)",
                    background: on ? "rgba(110,168,254,0.08)" : "transparent",
                    cursor: "pointer",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={(e) =>
                      setConsentGrants((prev) => ({ ...prev, [s.scope]: e.target.checked }))
                    }
                    style={{ marginTop: 3 }}
                  />
                  <div>
                    <strong style={{ display: "block", fontSize: 15 }}>{s.label}</strong>
                    <span className="muted" style={{ fontSize: 13 }}>{s.description}</span>
                  </div>
                </label>
              );
            })}
          </div>
          <label
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: 10,
              padding: "10px 2px 14px",
              fontSize: 13,
            }}
          >
            <input
              type="checkbox"
              checked={consentAck}
              onChange={(e) => setConsentAck(e.target.checked)}
              style={{ marginTop: 3 }}
            />
            <span>
              I understand the choices above, and that I can change them later. See the{" "}
              <a href="/legal" target="_blank" rel="noreferrer">Legal hub</a> for the full
              Privacy Policy and Terms.
            </span>
          </label>
          {error && <p className={styles.error} role="alert">{error}</p>}
          <div className={styles.actions}>
            <button
              className={styles.primary}
              disabled={busy || !consentAck}
              onClick={() => void saveConsent()}
            >
              {busy ? "Saving…" : consentAck ? "Continue" : "Acknowledge to continue"}
            </button>
            <button className={styles.ghost} onClick={() => setStep("learn")}>
              Back
            </button>
          </div>
        </section>
      )}

      {step === "plan" && (
        <section className={styles.panel}>
          <span className={styles.eyebrow}>Last step</span>
          <h1>Pick a plan to start.</h1>
          <p className={styles.lede}>
            {freeOffer
              ? "Free is a 14-day English trial for the first 100 people. It does not include group classes or AI agents, and then it goes away. Paid plans add those."
              : "The free plan has ended. Choose a paid plan to continue."}
          </p>
          <div className={styles.plans}>
            {consumerPlans.filter((item) => freeOffer || item.tier !== "free").map((item) => (
              <button
                key={item.tier}
                type="button"
                className={`${styles.plan} ${plan === item.tier ? styles.planOn : ""}`}
                onClick={() => setPlan(item.tier)}
              >
                <strong>{item.display_name}</strong>
                <span className={styles.planPrice}>{formatMonthlyPrice(item)}</span>
                {item.tier === "premium" && <span className={styles.vip}>VIP</span>}
                <small>{item.blurb}</small>
              </button>
            ))}
          </div>
          <p className={styles.note}>
            Membership is billed monthly (Standard $19/month). Unlocking a full course is a separate
            one-time $19.99 charge — see <a href="/billing">billing</a>.
          </p>
          {error && <p className={styles.error} role="alert">{error}</p>}
          <div className={styles.actions}>
            <button className={styles.primary} disabled={busy} onClick={() => void savePlan()}>
              {busy ? "Finishing…" : plan === "free" ? "Start learning" : "Continue to payment"}
            </button>
            <button className={styles.ghost} onClick={() => setStep("identity")}>Back</button>
          </div>
        </section>
      )}

      {step === "payment" && (
        <section className={styles.panel}>
          <span className={styles.eyebrow}>Payment</span>
          <h1>{t("onboarding.paymentTitle")}</h1>
          <p className={styles.note}>{t("onboarding.paymentNote")}</p>
          <div className={styles.billing}>
            <input placeholder="Street address" value={billing.line1}
              onChange={(e) => setBilling({ ...billing, line1: e.target.value })} />
            <div className={styles.billingRow}>
              <input placeholder="City" value={billing.city}
                onChange={(e) => setBilling({ ...billing, city: e.target.value })} />
              <input placeholder="State" value={billing.state}
                onChange={(e) => setBilling({ ...billing, state: e.target.value })} />
              <input placeholder="ZIP" value={billing.postal_code}
                onChange={(e) => setBilling({ ...billing, postal_code: e.target.value })} />
            </div>
            <input
              inputMode="numeric"
              autoComplete="cc-number"
              placeholder="Card number"
              value={billing.card_number}
              onChange={(e) => setBilling({ ...billing, card_number: e.target.value })}
            />
            <div className={styles.billingRow}>
              <input
                inputMode="numeric"
                autoComplete="cc-exp-month"
                placeholder="Exp month"
                value={billing.exp_month || ""}
                onChange={(e) => setBilling({ ...billing, exp_month: Number(e.target.value.replace(/\D/g, "").slice(0, 2)) })}
              />
              <input
                inputMode="numeric"
                autoComplete="cc-exp-year"
                placeholder="Exp year"
                value={billing.exp_year || ""}
                onChange={(e) => setBilling({ ...billing, exp_year: Number(e.target.value.replace(/\D/g, "").slice(0, 4)) })}
              />
              <input
                inputMode="numeric"
                autoComplete="cc-csc"
                placeholder="CVV"
                value={billing.cvv}
                onChange={(e) => setBilling({ ...billing, cvv: e.target.value.replace(/\D/g, "").slice(0, 4) })}
              />
            </div>
          </div>
          {error && <p className={styles.error} role="alert">{error}</p>}
          <div className={styles.actions}>
            <button className={styles.primary} disabled={busy} onClick={() => void savePayment()}>
              {busy ? "Validating…" : "Validate and start learning"}
            </button>
            <button className={styles.ghost} onClick={() => setStep("plan")}>Back</button>
          </div>
        </section>
      )}
        </div>
      </div>
    </main>
  );
}
