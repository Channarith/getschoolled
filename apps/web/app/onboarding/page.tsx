"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import AvatarImage from "../components/AvatarImage";
import BiometricSetupAssistant from "../components/BiometricSetupAssistant";
import { AGE_MAX, AGE_MIN, AGE_OPTIONS, clampAge } from "../lib/learnerCheck";
import AccountStep from "./AccountStep";
import {
  AUTH_EVENT,
  completeOnboarding,
  getFreePlanOffer,
  getMe,
  getOnboardingStatus,
  getToken,
  selectOnboardingPlan,
  submitLearningProfile,
  submitOnboardingBilling,
  submitOnboardingLearner,
  submitOnboardingSurveyAnalytics,
} from "../lib/api";
import styles from "./Onboarding.module.css";

const PLANS = [
  { id: "free", label: "Free", price: "$0", vip: false, blurb: "14 days of English lessons with ads. No group classes or AI agents. First 100 people, then it goes away." },
  { id: "basic", label: "Basic", price: "$9/mo", vip: false, blurb: "5 languages, with ads" },
  { id: "pro", label: "Pro", price: "$19/mo", vip: true, blurb: "All languages, ad-free, solo classes" },
  { id: "premium", label: "Premium", price: "$29/mo", vip: true, blurb: "Everything + analytics" },
] as const;

const MODES = [
  { id: "video", art: "mode-video", label: "Watching videos", blurb: "Short lessons you can pause and replay." },
  { id: "live_teacher", art: "mode-person", label: "A live teacher", blurb: "Learning in person or in a live class." },
  { id: "presentation", art: "mode-presentation", label: "Presentations", blurb: "Slides and visual walkthroughs." },
  { id: "reading", art: "mode-reading", label: "Reading a book", blurb: "Taking your time with text and notes." },
  { id: "tutoring", art: "mode-tutoring", label: "1:1 tutoring", blurb: "One coach, just for you." },
  { id: "gaming", art: "mode-gaming", label: "Gaming", blurb: "Learning by playing and doing." },
] as const;
type ModeId = (typeof MODES)[number]["id"];

type Step = "account" | "about" | "learn" | "identity" | "plan" | "payment";
const BASE_STEPS: Step[] = ["about", "learn", "identity", "plan"];
const STEP_LABEL: Record<Step, string> = {
  account: "Your account",
  about: "About you",
  learn: "How you learn",
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
  plan: "onboarding_plan",
};

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
  const router = useRouter();
  const [step, setStep] = useState<Step>("about");
  const [includeAccount, setIncludeAccount] = useState(false);
  const [name, setName] = useState("");
  const [age, setAge] = useState<number | "">("");
  const [avatarId, setAvatarId] = useState<string | undefined>();
  const ageRef = useRef<HTMLSelectElement>(null);
  const [ratings, setRatings] = useState<Partial<Record<ModeId, number>>>({});
  const [focus, setFocus] = useState<ModeId>("video");
  const [studentId, setStudentId] = useState("");
  const [plan, setPlan] = useState("free");
  const [freeOffer, setFreeOffer] = useState(true);
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
    if (saved && known && saved !== "account" && (saved === "about" || savedStudent)) setStep(saved);
    const savedName = localStorage.getItem(STORAGE.name) || "";
    setName(savedName);
    getMe().then((me) => {
      setAvatarId(me.avatar_id);
      if (!savedName && me.display_name) setName((current) => current || me.display_name);
    }).catch(() => undefined);
    const savedAge = Number(localStorage.getItem(STORAGE.age));
    if (savedAge) setAge(savedAge);
    setRatings(readJson(STORAGE.ratings, {}));
    setStudentId(savedStudent);
    setPlan(localStorage.getItem(STORAGE.plan) || "free");
    getFreePlanOffer().then((offer) => {
      setFreeOffer(offer.available);
      if (!offer.available) {
        setPlan((current) => (current === "free" ? "basic" : current));
      }
    }).catch(() => undefined);
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
      setStep("learn");
    });
  }

  const rated = MODES.filter((mode) => ratings[mode.id] != null).length;
  const top = [...MODES].sort((a, b) => (ratings[b.id] ?? 0) - (ratings[a.id] ?? 0))[0];

  function rate(mode: ModeId, value: number) {
    setRatings((current) => ({ ...current, [mode]: value }));
    setFocus(mode);
  }

  function saveLearning() {
    return run(async () => {
      const answers = { modality_ratings: ratings };
      await submitLearningProfile(studentId, answers);
      const me = await getMe().catch(() => null);
      if (me) {
        void submitOnboardingSurveyAnalytics({ account_id: me.id, student_id: studentId, answers })
          .catch(() => undefined);
      }
      window.dispatchEvent(new CustomEvent("aoep-learning-profile-saved"));
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
      await submitOnboardingBilling({ ...billing });
      await selectOnboardingPlan(plan);
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

  if (step === "identity" && studentId) {
    return (
      <BiometricSetupAssistant
        studentId={studentId}
        ageBand={ageBand}
        stepLabel={stepLabel}
        onBack={() => setStep("learn")}
        onComplete={() => setStep("plan")}
        onSkip={() => setStep("plan")}
      />
    );
  }

  const art = step === "account" ? "account" : step === "about" ? "about" : step === "learn" ? "learn" : "plan";

  return (
    <main className={styles.shell} data-step={step}>
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
        {step !== "learn" && (
          <div className={styles.artPane} aria-hidden="true">
            <Image key={art} className={styles.art} src={`/setup-assistant/${art}.webp`} alt="" fill priority sizes="50vw" />
          </div>
        )}
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
            <div className={styles.nameRow}>
              <AvatarImage avatarId={avatarId} size={52} alt="" className={styles.avatar} />
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
              The name on your profile and avatar. A nickname is fine. It doesn’t need to be your legal name.
            </small>
          </label>
          <div className={styles.field}>
            <span id="age-label">How old are you?</span>
            <div className={styles.ageRow}>
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
            <button className={styles.primary} disabled={busy || !aboutReady} onClick={() => void saveAbout()}>
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
          <div className={styles.modes}>
            {MODES.map((mode) => {
              const value = ratings[mode.id];
              return (
                <article
                  key={mode.id}
                  className={`${styles.mode} ${focus === mode.id ? styles.modeFocus : ""}`}
                  onMouseEnter={() => setFocus(mode.id)}
                  onFocus={() => setFocus(mode.id)}
                >
                  <div className={styles.modeArt}>
                    <Image src={`/setup-assistant/${mode.art}.webp`} alt="" fill sizes="(max-width: 860px) 50vw, 240px" />
                    {value != null && <span className={styles.modeScore}>{value}</span>}
                  </div>
                  <div className={styles.modeBody}>
                    <h3>{mode.label}</h3>
                    <p>{mode.blurb}</p>
                    <div className={styles.scale} role="radiogroup" aria-label={`Rate ${mode.label} from 1 to 10`}>
                      {Array.from({ length: 10 }, (_, index) => index + 1).map((n) => (
                        <button
                          key={n}
                          type="button"
                          role="radio"
                          aria-checked={value === n}
                          aria-label={`${n}`}
                          className={value != null && n <= value ? styles.scaleOn : ""}
                          onClick={() => rate(mode.id, n)}
                        >{n}</button>
                      ))}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
          {error && <p className={styles.error} role="alert">{error}</p>}
          <div className={styles.actions}>
            <button className={styles.primary} disabled={busy || rated < MODES.length} onClick={() => void saveLearning()}>
              {busy ? "Saving…" : rated < MODES.length ? `Rate ${MODES.length - rated} more` : "Continue"}
            </button>
            <button className={styles.ghost} onClick={() => setStep("about")}>Back</button>
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
            {PLANS.filter((item) => freeOffer || item.id !== "free").map((item) => (
              <button
                key={item.id}
                type="button"
                className={`${styles.plan} ${plan === item.id ? styles.planOn : ""}`}
                onClick={() => setPlan(item.id)}
              >
                <strong>{item.label}</strong>
                <span className={styles.planPrice}>{item.price}</span>
                {item.vip && <span className={styles.vip}>VIP</span>}
                <small>{item.blurb}</small>
              </button>
            ))}
          </div>
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
          <h1>Add a payment method.</h1>
          {/* SECURITY: replace with Stripe.js Elements before production so raw card data never reaches our backend. */}
          <p className={styles.note}>Demo mode: no real charge is made. Use a test card such as 4111 1111 1111 1111.</p>
          <div className={styles.billing}>
            <input placeholder="Card number" value={billing.card_number}
              onChange={(e) => setBilling({ ...billing, card_number: e.target.value })} />
            <div className={styles.billingRow}>
              <input type="number" placeholder="MM" value={billing.exp_month}
                onChange={(e) => setBilling({ ...billing, exp_month: Number(e.target.value) })} />
              <input type="number" placeholder="YYYY" value={billing.exp_year}
                onChange={(e) => setBilling({ ...billing, exp_year: Number(e.target.value) })} />
              <input placeholder="CVV" value={billing.cvv}
                onChange={(e) => setBilling({ ...billing, cvv: e.target.value })} />
            </div>
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
