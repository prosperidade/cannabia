import { cn } from "@/lib/cn";

const sizeMap = {
  sm: "text-sm",
  md: "text-base",
  lg: "text-2xl",
  xl: "text-4xl",
} as const;

export interface MaterialIconProps {
  icon: string;
  filled?: boolean;
  size?: keyof typeof sizeMap;
  className?: string;
}

export function MaterialIcon({
  icon,
  filled = false,
  size = "md",
  className,
}: MaterialIconProps) {
  return (
    <span
      className={cn("material-symbols-outlined", sizeMap[size], className)}
      style={
        filled
          ? { fontVariationSettings: "'FILL' 1, 'wght' 400, 'GRAD' 0, 'opsz' 24" }
          : { fontVariationSettings: "'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24" }
      }
    >
      {icon}
    </span>
  );
}
