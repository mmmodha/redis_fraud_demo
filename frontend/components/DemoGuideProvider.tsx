"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  GUIDE_STEPS,
  eventsMatch,
  type GuideEvent,
  type GuideStep,
  type HeroKey,
} from "@/lib/demoGuide";

const STORAGE_KEY = "fcc-guide-mode";

type RunHeroFn = (heroKey: HeroKey) => void;
type SelectHeroFn = (heroKey: HeroKey) => void;
type InsertChatFn = (text: string) => void;

type DemoGuideContextValue = {
  guideMode: boolean;
  setGuideMode: (on: boolean) => void;
  currentStepIndex: number;
  currentStep: GuideStep | null;
  completeAction: (event: GuideEvent) => void;
  continueStep: () => void;
  skipStep: () => void;
  resetGuide: () => void;
  registerRunHero: (fn: RunHeroFn) => void;
  registerSelectHero: (fn: SelectHeroFn) => void;
  registerInsertChat: (fn: InsertChatFn) => void;
  runHeroForGuide: (heroKey: HeroKey) => void;
  insertChatMessage: (text: string) => void;
  scoreReadyForHero: HeroKey | null;
  setScoreReadyForHero: (hero: HeroKey | null) => void;
  cacheHitForHero: HeroKey | null;
  setCacheHitForHero: (hero: HeroKey | null) => void;
  otpConfirmedForSarah: boolean;
  setOtpConfirmedForSarah: (v: boolean) => void;
  isScoringHero: HeroKey | null;
  setIsScoringHero: (hero: HeroKey | null) => void;
  isChatLoading: boolean;
  setIsChatLoading: (v: boolean) => void;
};

const DemoGuideContext = createContext<DemoGuideContextValue | null>(null);

export function DemoGuideProvider({ children }: { children: ReactNode }) {
  const [guideMode, setGuideModeState] = useState(false);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [scoreReadyForHero, setScoreReadyForHero] = useState<HeroKey | null>(null);
  const [cacheHitForHero, setCacheHitForHero] = useState<HeroKey | null>(null);
  const [otpConfirmedForSarah, setOtpConfirmedForSarah] = useState(false);
  const [isScoringHero, setIsScoringHero] = useState<HeroKey | null>(null);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const runHeroRef = useRef<RunHeroFn | null>(null);
  const selectHeroRef = useRef<SelectHeroFn | null>(null);
  const insertChatRef = useRef<InsertChatFn | null>(null);
  const prevStepIdRef = useRef<string | null>(null);
  const prevStepHeroRef = useRef<HeroKey | undefined>(undefined);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === "true") setGuideModeState(true);
    } catch {
      /* ignore */
    }
  }, []);

  const advance = useCallback(() => {
    setCurrentStepIndex((i) => Math.min(i + 1, GUIDE_STEPS.length - 1));
  }, []);

  const setGuideMode = useCallback((on: boolean) => {
    setGuideModeState(on);
    try {
      localStorage.setItem(STORAGE_KEY, on ? "true" : "false");
    } catch {
      /* ignore */
    }
    if (on) {
      setCurrentStepIndex(0);
      setScoreReadyForHero(null);
      setCacheHitForHero(null);
      setOtpConfirmedForSarah(false);
      setIsScoringHero(null);
      setIsChatLoading(false);
      prevStepIdRef.current = null;
      prevStepHeroRef.current = undefined;
    }
  }, []);

  const advanceIfMatch = useCallback(
    (event: GuideEvent) => {
      if (!guideMode) return;
      const step = GUIDE_STEPS[currentStepIndex];
      if (!step || step.advance.mode !== "event") return;
      if (!eventsMatch(step, event)) return;
      const delayMs = event.type === "hero-cache-hit" ? 900 : 400;
      setTimeout(advance, delayMs);
    },
    [guideMode, currentStepIndex, advance],
  );

  const continueStep = useCallback(() => {
    if (!guideMode) return;
    const step = GUIDE_STEPS[currentStepIndex];
    if (!step || step.advance.mode !== "manual") return;
    advance();
  }, [guideMode, currentStepIndex, advance]);

  const skipStep = useCallback(() => {
    advance();
  }, [advance]);

  const resetGuide = useCallback(() => {
    setCurrentStepIndex(0);
    setScoreReadyForHero(null);
    setCacheHitForHero(null);
    setOtpConfirmedForSarah(false);
    setIsScoringHero(null);
    setIsChatLoading(false);
    prevStepIdRef.current = null;
    prevStepHeroRef.current = undefined;
  }, []);

  const registerRunHero = useCallback((fn: RunHeroFn) => {
    runHeroRef.current = fn;
  }, []);

  const registerSelectHero = useCallback((fn: SelectHeroFn) => {
    selectHeroRef.current = fn;
  }, []);

  const registerInsertChat = useCallback((fn: InsertChatFn) => {
    insertChatRef.current = fn;
  }, []);

  const runHeroForGuide = useCallback((heroKey: HeroKey) => {
    runHeroRef.current?.(heroKey);
  }, []);

  const insertChatMessage = useCallback((text: string) => {
    insertChatRef.current?.(text);
  }, []);

  const currentStep = guideMode ? GUIDE_STEPS[currentStepIndex] ?? null : null;

  // Activate hero and reset stale gates when step changes.
  useEffect(() => {
    if (!guideMode || !currentStep) return;
    if (currentStep.id === prevStepIdRef.current) return;

    const prevHero = prevStepHeroRef.current;
    prevStepIdRef.current = currentStep.id;
    prevStepHeroRef.current = currentStep.hero;

    if (currentStep.hero != null && prevHero != null && currentStep.hero !== prevHero) {
      setScoreReadyForHero(null);
      setCacheHitForHero(null);
      if (currentStep.hero !== "sarah") setOtpConfirmedForSarah(false);
    }

    if (currentStep.activateHero) {
      selectHeroRef.current?.(currentStep.activateHero);
    } else if (
      currentStep.suggestedAction === "run-hero" &&
      currentStep.hero
    ) {
      selectHeroRef.current?.(currentStep.hero);
    }
  }, [guideMode, currentStep]);

  const value = useMemo(
    (): DemoGuideContextValue => ({
      guideMode,
      setGuideMode,
      currentStepIndex,
      currentStep,
      completeAction: advanceIfMatch,
      continueStep,
      skipStep,
      resetGuide,
      registerRunHero,
      registerSelectHero,
      registerInsertChat,
      runHeroForGuide,
      insertChatMessage,
      scoreReadyForHero,
      setScoreReadyForHero,
      cacheHitForHero,
      setCacheHitForHero,
      otpConfirmedForSarah,
      setOtpConfirmedForSarah,
      isScoringHero,
      setIsScoringHero,
      isChatLoading,
      setIsChatLoading,
    }),
    [
      guideMode,
      setGuideMode,
      currentStepIndex,
      currentStep,
      advanceIfMatch,
      continueStep,
      skipStep,
      resetGuide,
      registerRunHero,
      registerSelectHero,
      registerInsertChat,
      runHeroForGuide,
      insertChatMessage,
      scoreReadyForHero,
      otpConfirmedForSarah,
      cacheHitForHero,
      isScoringHero,
      isChatLoading,
    ],
  );

  return (
    <DemoGuideContext.Provider value={value}>{children}</DemoGuideContext.Provider>
  );
}

export function useDemoGuide(): DemoGuideContextValue {
  const ctx = useContext(DemoGuideContext);
  if (!ctx) {
    throw new Error("useDemoGuide must be used within DemoGuideProvider");
  }
  return ctx;
}

export function useDemoGuideOptional(): DemoGuideContextValue | null {
  return useContext(DemoGuideContext);
}
