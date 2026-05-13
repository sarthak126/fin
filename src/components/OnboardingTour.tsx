"use client";

import {
  startTransition,
  useEffect,
  useEffectEvent,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { createPortal } from "react-dom";
import { Button } from "@/components/ui/button";
import { useOnboardingStore } from "@/store/onboarding";

type TourPlacement = "top" | "bottom" | "bottom-end";

type TourStep = {
  target: string;
  content: string;
  placement: TourPlacement;
};

type SpotlightBox = {
  top: number;
  left: number;
  width: number;
  height: number;
};

const TOUR_STEPS: TourStep[] = [
  {
    target: ".tour-step-quick-upload",
    content: "Start here to open a new underwriting case from anywhere in the dashboard.",
    placement: "bottom-end",
  },
  {
    target: "#analyze-doc-btn",
    content: "Use the main dashboard action to kick off a real underwriting case and launch AI review.",
    placement: "bottom",
  },
  {
    target: "#activity-feed-area",
    content: "Recent case activity and AI review progress show up here in real time.",
    placement: "top",
  },
  {
    target: "#view-all-cases-link",
    content: "Jump to the cases workspace to review active and completed underwriting cases in detail.",
    placement: "top",
  },
];

const VIEWPORT_PADDING = 16;
const SPOTLIGHT_PADDING = 10;
const TOOLTIP_GAP = 18;
const TOOLTIP_WIDTH = 340;
const TOOLTIP_HEIGHT_GUESS = 220;

function subscribeToHydration() {
  return () => undefined;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function getSpotlightBox(rect: DOMRect): SpotlightBox {
  return {
    top: Math.max(rect.top - SPOTLIGHT_PADDING, 8),
    left: Math.max(rect.left - SPOTLIGHT_PADDING, 8),
    width: rect.width + SPOTLIGHT_PADDING * 2,
    height: rect.height + SPOTLIGHT_PADDING * 2,
  };
}

function getTooltipPosition(
  spotlight: SpotlightBox | null,
  placement: TourPlacement,
): { top: number; left: number; width: number } {
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;
  const width = Math.min(TOOLTIP_WIDTH, viewportWidth - VIEWPORT_PADDING * 2);

  if (!spotlight) {
    return {
      top: Math.max(VIEWPORT_PADDING, (viewportHeight - TOOLTIP_HEIGHT_GUESS) / 2),
      left: Math.max(VIEWPORT_PADDING, (viewportWidth - width) / 2),
      width,
    };
  }

  const centeredLeft = spotlight.left + spotlight.width / 2 - width / 2;
  const endAlignedLeft = spotlight.left + spotlight.width - width;

  let top = spotlight.top + spotlight.height + TOOLTIP_GAP;
  const left = placement === "bottom-end" ? endAlignedLeft : centeredLeft;

  if (placement === "top") {
    top = spotlight.top - TOOLTIP_HEIGHT_GUESS - TOOLTIP_GAP;
  }

  return {
    top: clamp(top, VIEWPORT_PADDING, viewportHeight - TOOLTIP_HEIGHT_GUESS - VIEWPORT_PADDING),
    left: clamp(left, VIEWPORT_PADDING, viewportWidth - width - VIEWPORT_PADDING),
    width,
  };
}

export function OnboardingTour() {
  const { tourIsActive, stopTour } = useOnboardingStore();
  const mounted = useSyncExternalStore(subscribeToHydration, () => true, () => false);
  const [stepIndex, setStepIndex] = useState(0);
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const activeStepIndex = tourIsActive ? stepIndex : 0;
  const currentStep = TOUR_STEPS[activeStepIndex];

  const measureTarget = useEffectEvent(() => {
    if (!tourIsActive) {
      return;
    }

    const element = document.querySelector<HTMLElement>(currentStep.target);
    if (!element) {
      setTargetRect(null);
      return;
    }

    const rect = element.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) {
      setTargetRect(null);
      return;
    }

    setTargetRect(rect);
  });

  const focusCurrentTarget = useEffectEvent(() => {
    if (!tourIsActive) {
      return;
    }

    const element = document.querySelector<HTMLElement>(currentStep.target);
    if (!element) {
      setTargetRect(null);
      return;
    }

    element.scrollIntoView({
      behavior: "smooth",
      block: "center",
      inline: "nearest",
    });

    measureTarget();
  });

  useEffect(() => {
    if (!mounted || !tourIsActive) {
      return;
    }

    focusCurrentTarget();

    const timeoutId = window.setTimeout(() => {
      measureTarget();
    }, 300);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [activeStepIndex, mounted, tourIsActive]);

  useEffect(() => {
    if (!mounted || !tourIsActive) {
      return;
    }

    let frameId = 0;
    const scheduleMeasure = () => {
      window.cancelAnimationFrame(frameId);
      frameId = window.requestAnimationFrame(() => {
        measureTarget();
      });
    };

    window.addEventListener("resize", scheduleMeasure);
    window.addEventListener("scroll", scheduleMeasure, true);

    return () => {
      window.cancelAnimationFrame(frameId);
      window.removeEventListener("resize", scheduleMeasure);
      window.removeEventListener("scroll", scheduleMeasure, true);
    };
  }, [mounted, tourIsActive]);

  useEffect(() => {
    if (!mounted || !tourIsActive) {
      return;
    }

    dialogRef.current?.focus();
  }, [mounted, tourIsActive, stepIndex]);

  const finishTour = () => {
    stopTour();
    setStepIndex(0);
    setTargetRect(null);
  };

  const goToPreviousStep = () => {
    startTransition(() => {
      setStepIndex((current) => Math.max(0, current - 1));
    });
  };

  const goToNextStep = () => {
    if (activeStepIndex === TOUR_STEPS.length - 1) {
      finishTour();
      return;
    }

    startTransition(() => {
      setStepIndex((current) => Math.min(TOUR_STEPS.length - 1, current + 1));
    });
  };

  useEffect(() => {
    if (!mounted || !tourIsActive) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        stopTour();
        setStepIndex(0);
        setTargetRect(null);
        return;
      }

      if (event.key === "ArrowLeft" && activeStepIndex > 0) {
        startTransition(() => {
          setStepIndex((current) => Math.max(0, current - 1));
        });
        return;
      }

      if (event.key === "ArrowRight") {
        if (activeStepIndex === TOUR_STEPS.length - 1) {
          stopTour();
          setStepIndex(0);
          setTargetRect(null);
          return;
        }

        startTransition(() => {
          setStepIndex((current) => Math.min(TOUR_STEPS.length - 1, current + 1));
        });
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [activeStepIndex, mounted, stopTour, tourIsActive]);

  const spotlight = useMemo(
    () => (targetRect ? getSpotlightBox(targetRect) : null),
    [targetRect],
  );

  if (!mounted || !tourIsActive) {
    return null;
  }

  const tooltipPosition = getTooltipPosition(spotlight, currentStep.placement);
  const isLastStep = activeStepIndex === TOUR_STEPS.length - 1;

  return createPortal(
    <>
      <div className="fixed inset-0 z-[1000] bg-black/35" aria-hidden="true" />

      {spotlight ? (
        <div
          aria-hidden="true"
          className="pointer-events-none fixed z-[1001] rounded-2xl border border-primary/70 bg-white/5 transition-all duration-200"
          style={{
            top: spotlight.top,
            left: spotlight.left,
            width: spotlight.width,
            height: spotlight.height,
            boxShadow: "0 0 0 9999px rgba(9, 9, 11, 0.55)",
          }}
        />
      ) : null}

      <div
        ref={dialogRef}
        aria-label="Guided onboarding tour"
        aria-modal="true"
        role="dialog"
        tabIndex={-1}
        className="fixed z-[1002] rounded-2xl border border-[var(--border-card)] bg-[var(--background)] p-4 text-[var(--text-primary)] shadow-2xl shadow-black/30 outline-none"
        style={tooltipPosition}
      >
        <div className="mb-3 flex items-center justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">
            Guided Tour
          </span>
          <span className="text-[12px] font-medium text-[var(--text-tertiary)]">
            {activeStepIndex + 1}/{TOUR_STEPS.length}
          </span>
        </div>

        <div className="mb-4 h-1.5 overflow-hidden rounded-full bg-[var(--surface-secondary)]">
          <div
            className="h-full rounded-full bg-primary transition-all duration-300"
            style={{ width: `${((activeStepIndex + 1) / TOUR_STEPS.length) * 100}%` }}
          />
        </div>

        <p className="text-[14px] leading-relaxed text-[var(--text-secondary)]">
          {currentStep.content}
        </p>

        {!spotlight ? (
          <p className="mt-3 rounded-xl border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-[12px] leading-relaxed text-amber-700 dark:text-amber-300">
            This step&apos;s target is not visible on the current screen, so the tour is using a fallback view.
          </p>
        ) : null}

        <div className="mt-5 flex items-center justify-between gap-2">
          <Button
            variant="ghost"
            size="sm"
            type="button"
            onClick={finishTour}
            className="h-8 rounded-lg px-2 text-[12px] font-medium text-[var(--text-tertiary)] hover:bg-[var(--surface-secondary)] hover:text-[var(--text-primary)]"
          >
            Skip tour
          </Button>

          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              type="button"
              disabled={activeStepIndex === 0}
              onClick={goToPreviousStep}
              className="h-8 rounded-lg px-3 text-[12px] font-medium text-[var(--text-secondary)]"
            >
              Back
            </Button>
            <Button
              size="sm"
              type="button"
              onClick={goToNextStep}
              className="h-8 rounded-lg px-3 text-[12px] font-semibold"
            >
              {isLastStep ? "Finish tour" : "Next"}
            </Button>
          </div>
        </div>
      </div>
    </>,
    document.body,
  );
}
