import { Check, SlidersHorizontal } from "lucide-react";
import {
  Menu,
  MenuContent,
  MenuGroupLabel,
  MenuItemIndicator,
  MenuRadioGroup,
  MenuRadioItem,
  MenuTrigger,
} from "@ui-sdk/react/menu";
import { cn } from "@/lib/cn";
import { STEER_STOPS, steerStop, type SteerLevel } from "@/lib/steer";

/* Conversation mode controls the next response. Keep it beside the composer.
 * One choice of two, so a menu of radio items: arrow keys and typeahead move
 * between styles, the chosen one is announced as checked, and Escape or an
 * outside press closes it and returns focus to the trigger. */
export function SteerDial({
  value,
  onChange,
  className,
}: {
  value: SteerLevel;
  onChange: (next: SteerLevel) => void;
  className?: string;
}) {
  const stop = steerStop(value);

  return (
    <Menu>
      <MenuTrigger
        className={cn(
          "inline-flex size-11 shrink-0 items-center justify-center rounded-input text-text-muted transition-colors duration-fast hover:bg-zone-9 hover:text-text data-open:bg-zone-9 data-open:text-text",
          className,
        )}
        aria-label={`Assistant style: ${stop.label}`}
        title={`Assistant style: ${stop.label}`}
      >
        <SlidersHorizontal className="size-4 text-text-muted" aria-hidden />
      </MenuTrigger>
      <MenuContent side="top" align="start" sideOffset={8} collisionPadding={8} className="popup-panel w-64 p-2">
        <MenuRadioGroup
          value={stop.id}
          onValueChange={(id) => {
            const next = STEER_STOPS.find((option) => option.id === id);
            if (next) onChange(next.level);
          }}
          className="space-y-1"
        >
          <MenuGroupLabel className="type-label block px-2 pb-2 pt-1 text-text">Assistant style</MenuGroupLabel>
          {STEER_STOPS.map((option) => (
            <MenuRadioItem
              key={option.id}
              value={option.id}
              label={option.label}
              closeOnSelect
              className="popup-item items-start gap-2 px-2 py-2 data-checked:bg-accent-wash"
            >
              <span className="mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-dot border border-control-edge bg-surface">
                <MenuItemIndicator>
                  <Check className="size-3 text-accent" aria-hidden />
                </MenuItemIndicator>
              </span>
              <span className="min-w-0">
                <span className="type-control block text-text">{option.label}</span>
                <span className="type-caption block text-text-muted">{option.summary}</span>
              </span>
            </MenuRadioItem>
          ))}
        </MenuRadioGroup>
      </MenuContent>
    </Menu>
  );
}
