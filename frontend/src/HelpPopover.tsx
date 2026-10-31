import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { CircleHelp, X } from "lucide-react";

export function HelpPopover() {
  const [open, setOpen] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [position, setPosition] = useState({ left: 16, top: 16 });
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const suppressFocus = useRef(false);
  const id = useId();
  function clearTimer() {
    clearTimeout(timer.current);
  }
  function show() {
    clearTimer();
    setOpen(true);
  }
  function close(returnFocus = false) {
    clearTimer();
    setOpen(false);
    setPinned(false);
    if (returnFocus && document.activeElement !== trigger.current) {
      suppressFocus.current = true;
      trigger.current?.focus({ preventScroll: true });
    }
  }
  function hideSoon() {
    if (!pinned) {
      clearTimer();
      timer.current = setTimeout(() => setOpen(false), 150);
    }
  }
  useEffect(() => () => clearTimeout(timer.current), []);
  useLayoutEffect(() => {
    if (!open) return;
    function place() {
      if (!trigger.current || !panel.current) return;
      const anchor = trigger.current.getBoundingClientRect();
      const bounds = panel.current.getBoundingClientRect();
      const mobile = window.innerWidth <= 700;
      const left = mobile ? anchor.left : anchor.right + 12;
      const top = mobile ? anchor.bottom + 8 : anchor.bottom - bounds.height;
      setPosition({
        left: Math.max(
          16,
          Math.min(left, window.innerWidth - bounds.width - 16),
        ),
        top: Math.max(
          16,
          Math.min(top, window.innerHeight - bounds.height - 16),
        ),
      });
    }
    place();
    if (pinned) panel.current?.focus({ preventScroll: true });
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [open, pinned]);
  useEffect(() => {
    if (!open) return;
    function outside(event: PointerEvent) {
      if (
        !panel.current?.contains(event.target as Node) &&
        !trigger.current?.contains(event.target as Node)
      )
        close();
    }
    function escape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        close(true);
      }
    }
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);
  return (
    <>
      <button
        ref={trigger}
        type="button"
        className="help-trigger"
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-controls={open ? id : undefined}
        aria-describedby={open && !pinned ? id : undefined}
        onPointerEnter={(e) => {
          if (e.pointerType === "mouse") show();
        }}
        onPointerLeave={hideSoon}
        onFocus={() => {
          if (suppressFocus.current) suppressFocus.current = false;
          else show();
        }}
        onBlur={(e) => {
          if (!panel.current?.contains(e.relatedTarget as Node)) hideSoon();
        }}
        onClick={() => {
          if (pinned) close(true);
          else {
            clearTimer();
            setOpen(true);
            setPinned(true);
          }
        }}
      >
        <CircleHelp size={18} />
        Как это работает
      </button>
      {open &&
        createPortal(
          <section
            ref={panel}
            id={id}
            className="workspace-help-popover"
            style={position}
            role={pinned ? "dialog" : "tooltip"}
            aria-labelledby={pinned ? id + "-title" : undefined}
            tabIndex={-1}
            onPointerEnter={show}
            onPointerLeave={hideSoon}
          >
            <strong id={id + "-title"}>Как устроена работа</strong>
            {pinned && (
              <button
                type="button"
                className="help-close"
                aria-label="Закрыть подсказку"
                onClick={() => close(true)}
              >
                <X size={18} />
              </button>
            )}
            <p>
              Откройте событие → прочитайте классификацию и регламент → примите
              решение → выполните действие самостоятельно → отметьте результат.
              В «Источниках» можно переключить учебный сценарий.
            </p>
          </section>,
          document.body,
        )}
    </>
  );
}
