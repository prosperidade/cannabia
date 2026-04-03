import { clsx, type ClassValue } from "clsx";

/** Merge class names — wrapper sobre clsx para uso consistente no Design System. */
export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}
