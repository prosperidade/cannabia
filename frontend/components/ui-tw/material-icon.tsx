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
  /**
   * Rótulo acessível. Quando omitido (default), o ícone é puramente
   * decorativo: `aria-hidden` impede que o leitor de tela vocalize a
   * ligature ("eco", "dashboard"...). Quando fornecido, o ícone passa a
   * ser semântico (`role="img"` + `aria-label`).
   */
  label?: string;
}

export function MaterialIcon({
  icon,
  filled = false,
  size = "md",
  className,
  label,
}: MaterialIconProps) {
  const semantic = label !== undefined;
  return (
    <span
      className={cn("material-symbols-outlined", sizeMap[size], className)}
      aria-hidden={semantic ? undefined : true}
      role={semantic ? "img" : undefined}
      aria-label={semantic ? label : undefined}
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
